"""Background reconciler for launch job status polling."""

import threading
import time
from typing import Dict, Any, List
from datetime import datetime

from ..utils import get_logger
from .launch_service import LaunchService

logger = get_logger(__name__)


class LaunchReconciler:
    """Background service for reconciling launch job statuses."""
    
    def __init__(self, launch_service: LaunchService, interval_seconds: int = 30):
        """Initialize launch reconciler.
        
        Args:
            launch_service: LaunchService instance
            interval_seconds: Polling interval in seconds
        """
        self._launch_service = launch_service
        self._interval_seconds = interval_seconds
        self._running = False
        self._thread = None
        self._stop_event = threading.Event()
    
    def start_background_thread(self) -> None:
        """Start background reconciliation loop."""
        if self._running:
            logger.warning("Launch reconciler is already running")
            return
        
        self._running = True
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._reconciliation_loop, daemon=True)
        self._thread.start()
        logger.info(f"Launch reconciler started with {self._interval_seconds}s interval")
    
    def stop_background_thread(self) -> None:
        """Stop background reconciliation loop."""
        if not self._running:
            return
        
        self._running = False
        self._stop_event.set()
        
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
        
        logger.info("Launch reconciler stopped")
    
    def _reconciliation_loop(self) -> None:
        """Main reconciliation loop."""
        while self._running and not self._stop_event.is_set():
            try:
                self.reconcile_once()
            except Exception as e:
                logger.error(f"Error in reconciliation loop: {e}")
            
            # Wait for interval or stop event
            self._stop_event.wait(self._interval_seconds)
    
    def reconcile_once(self) -> None:
        """Poll all non-terminal launch jobs and update their status."""
        try:
            # Get all jobs with status in ['queued', 'running']
            filters = {'status': 'queued'}
            queued_jobs = self._launch_service._db.list_launch_jobs(filters=filters, limit=100)
            
            filters = {'status': 'running'}
            running_jobs = self._launch_service._db.list_launch_jobs(filters=filters, limit=100)
            
            all_jobs = queued_jobs + running_jobs
            
            if not all_jobs:
                return
            
            logger.debug(f"Reconciling {len(all_jobs)} launch jobs")
            
            for job in all_jobs:
                try:
                    self._reconcile_job(job)
                except Exception as e:
                    logger.error(f"Failed to reconcile job {job['job_id']}: {e}")
                    
        except Exception as e:
            logger.error(f"Error in reconcile_once: {e}")
    
    def _reconcile_job(self, job: Dict[str, Any]) -> None:
        """Reconcile a single launch job.
        
        Args:
            job: Launch job dictionary
        """
        job_id = job['job_id']
        status = job['status']
        deployment_id = job.get('deployment_id')
        method = job.get('method')
        
        # Skip jobs without deployment_id (they haven't started yet)
        if not deployment_id:
            return
        
        # Skip jobs that are already terminal
        if status in ['completed', 'failed', 'cancelled']:
            return
        
        try:
            # Poll adapter for status
            result = self._launch_service.poll_job_status(job_id)
            
            if not result.get('success'):
                logger.warning(f"Failed to poll status for job {job_id}: {result.get('error')}")
                return
            
            new_status = result.get('status')
            endpoint = result.get('endpoint')
            error = result.get('error')
            
            # Update job status if it changed
            if new_status != status:
                update_fields = {'status': new_status}
                
                if endpoint:
                    update_fields['endpoint_url'] = endpoint
                
                if error:
                    update_fields['error_message'] = error
                
                if new_status in ['completed', 'failed', 'cancelled']:
                    update_fields['completed_at'] = datetime.now().isoformat()
                
                self._launch_service._db.update_launch_job(job_id, **update_fields)
                
                logger.info(f"Updated job {job_id} status from {status} to {new_status}")
                
                # Log endpoint registration
                if new_status == 'completed' and endpoint:
                    logger.info(f"Job {job_id} completed with endpoint: {endpoint}")
                    
        except Exception as e:
            logger.error(f"Error reconciling job {job_id}: {e}")
    
    def get_status(self) -> Dict[str, Any]:
        """Get reconciler status.
        
        Returns:
            Dictionary with reconciler status information
        """
        return {
            'running': self._running,
            'interval_seconds': self._interval_seconds,
            'thread_alive': self._thread.is_alive() if self._thread else False
        }
    
    def force_reconcile_job(self, job_id: str) -> Dict[str, Any]:
        """Force reconciliation of a specific job.
        
        Args:
            job_id: Job identifier
            
        Returns:
            Dictionary with reconciliation result
        """
        try:
            job = self._launch_service._db.get_launch_job(job_id)
            if not job:
                return {
                    'success': False,
                    'error': f'Job not found: {job_id}'
                }
            
            self._reconcile_job(job)
            
            # Get updated job status
            updated_job = self._launch_service._db.get_launch_job(job_id)
            
            return {
                'success': True,
                'job': updated_job
            }
            
        except Exception as e:
            error_msg = f"Force reconcile failed: {str(e)}"
            logger.error(error_msg)
            return {
                'success': False,
                'error': error_msg
            }
    
    def get_reconciliation_stats(self) -> Dict[str, Any]:
        """Get reconciliation statistics.
        
        Returns:
            Dictionary with reconciliation statistics
        """
        try:
            # Count jobs by status
            all_jobs = self._launch_service._db.list_launch_jobs(limit=1000)
            
            stats = {
                'total_jobs': len(all_jobs),
                'by_status': {},
                'by_method': {},
                'recent_jobs': []
            }
            
            # Count by status and method
            for job in all_jobs:
                status = job.get('status', 'unknown')
                method = job.get('method', 'unknown')
                
                stats['by_status'][status] = stats['by_status'].get(status, 0) + 1
                stats['by_method'][method] = stats['by_method'].get(method, 0) + 1
            
            # Get recent jobs (last 10)
            recent_jobs = sorted(all_jobs, key=lambda x: x.get('created_at', ''), reverse=True)[:10]
            stats['recent_jobs'] = [
                {
                    'job_id': job['job_id'],
                    'method': job.get('method'),
                    'model_key': job.get('model_key'),
                    'status': job.get('status'),
                    'created_at': job.get('created_at')
                }
                for job in recent_jobs
            ]
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting reconciliation stats: {e}")
            return {
                'error': str(e)
            }
