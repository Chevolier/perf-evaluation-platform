"""Unified launch service for orchestrating model deployments."""

import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime

from core.models import model_registry
from core.launch_schemas import validate_launch_params, get_default_params
from core.constants import LaunchMethod, LaunchStatus
from utils import get_logger, DatabaseManager
from services.launch_adapters import (
    EMDLaunchAdapter, 
    HyperPodLaunchAdapter, 
    EKSLaunchAdapter, 
    EC2LaunchAdapter
)

logger = get_logger(__name__)


class LaunchService:
    """Service for managing unified model launches."""
    
    def __init__(self):
        """Initialize launch service."""
        self._db = DatabaseManager()
        self._registry = model_registry
        self._adapters = {
            LaunchMethod.SAGEMAKER_ENDPOINT.value: EMDLaunchAdapter(self),
            LaunchMethod.HYPERPOD.value: HyperPodLaunchAdapter(self),
            LaunchMethod.EKS.value: EKSLaunchAdapter(self),
            LaunchMethod.EC2.value: EC2LaunchAdapter(self)
        }
    
    def create_launch(self, method: str, model_key: str, engine: str, 
                     params: Dict[str, Any], user_id: Optional[str] = None) -> Dict[str, Any]:
        """Create and start a launch job.
        
        Args:
            method: Launch method (SAGEMAKER_ENDPOINT, HYPERPOD, EKS, EC2)
            model_key: Model to launch
            engine: Inference engine (vllm, sglang, etc.)
            params: Method-specific parameters
            user_id: User identifier (optional)
            
        Returns:
            Dictionary with job information or error
        """
        try:
            # 1. Validate method exists
            if method not in self._adapters:
                return {
                    'success': False,
                    'error': f'Unknown launch method: {method}'
                }
            
            # 2. Validate model exists and supports method/engine
            if not self._registry.get_model_info(model_key):
                return {
                    'success': False,
                    'error': f'Model not found: {model_key}'
                }
            
            supported_methods = self._registry.get_supported_methods(model_key)
            if method not in supported_methods:
                return {
                    'success': False,
                    'error': f'Model {model_key} does not support method {method}. Supported: {supported_methods}'
                }
            
            supported_engines = self._registry.get_supported_engines(model_key)
            if engine not in supported_engines:
                return {
                    'success': False,
                    'error': f'Model {model_key} does not support engine {engine}. Supported: {supported_engines}'
                }
            
            # 3. Validate parameters
            is_valid, error_msg = validate_launch_params(method, params)
            if not is_valid:
                return {
                    'success': False,
                    'error': f'Invalid parameters: {error_msg}'
                }
            
            # 4. Generate job_id
            job_id = str(uuid.uuid4())
            
            # 5. Create launch_jobs record
            self._db.create_launch_job(
                job_id=job_id,
                method=method,
                model_key=model_key,
                engine=engine,
                params=params,
                user_id=user_id
            )
            
            # 6. Dispatch to appropriate adapter
            adapter = self._adapters[method]
            result = adapter.execute(job_id, model_key, engine, params)
            
            if result.get('success'):
                logger.info(f"Launch job {job_id} started successfully for {model_key} via {method}")
                return {
                    'success': True,
                    'job_id': job_id,
                    'method': method,
                    'model_key': model_key,
                    'engine': engine,
                    'status': 'queued'
                }
            else:
                # Job creation failed, but record exists - update status
                self._db.update_launch_job(
                    job_id, 
                    status='failed', 
                    error_message=result.get('error', 'Launch failed'),
                    completed_at=datetime.now().isoformat()
                )
                return {
                    'success': False,
                    'error': result.get('error', 'Launch failed'),
                    'job_id': job_id
                }
                
        except Exception as e:
            error_msg = f"Launch creation failed: {str(e)}"
            logger.error(error_msg)
            return {
                'success': False,
                'error': error_msg
            }
    
    def get_launch_status(self, job_id: str) -> Dict[str, Any]:
        """Get current status of a launch job.
        
        Args:
            job_id: Job identifier
            
        Returns:
            Dictionary with job status information
        """
        try:
            job = self._db.get_launch_job(job_id)
            if not job:
                return {
                    'success': False,
                    'error': f'Job not found: {job_id}'
                }
            
            return {
                'success': True,
                'job': job
            }
            
        except Exception as e:
            error_msg = f"Failed to get launch status: {str(e)}"
            logger.error(error_msg)
            return {
                'success': False,
                'error': error_msg
            }
    
    def list_launches(self, filters: Optional[Dict[str, Any]] = None, 
                     limit: int = 50, offset: int = 0) -> Dict[str, Any]:
        """List launch jobs with pagination.
        
        Args:
            filters: Optional filters (method, status, model_key, user_id)
            limit: Maximum number of results
            offset: Number of results to skip
            
        Returns:
            Dictionary with list of jobs and pagination info
        """
        try:
            jobs = self._db.list_launch_jobs(filters=filters, limit=limit, offset=offset)
            
            return {
                'success': True,
                'jobs': jobs,
                'pagination': {
                    'limit': limit,
                    'offset': offset,
                    'count': len(jobs)
                }
            }
            
        except Exception as e:
            error_msg = f"Failed to list launches: {str(e)}"
            logger.error(error_msg)
            return {
                'success': False,
                'error': error_msg
            }
    
    def cancel_launch(self, job_id: str) -> Dict[str, Any]:
        """Cancel a running launch job.
        
        Args:
            job_id: Job identifier
            
        Returns:
            Dictionary with cancellation result
        """
        try:
            job = self._db.get_launch_job(job_id)
            if not job:
                return {
                    'success': False,
                    'error': f'Job not found: {job_id}'
                }
            
            status = job.get('status')
            if status in ['completed', 'failed', 'cancelled']:
                return {
                    'success': False,
                    'error': f'Cannot cancel job in status: {status}'
                }
            
            # Update status to cancelled
            self._db.update_launch_job(
                job_id,
                status='cancelled',
                completed_at=datetime.now().isoformat()
            )
            
            # Attempt cleanup if we have a deployment_id
            deployment_id = job.get('deployment_id')
            if deployment_id:
                method = job.get('method')
                if method in self._adapters:
                    adapter = self._adapters[method]
                    try:
                        adapter.cleanup(job_id, deployment_id)
                    except Exception as cleanup_error:
                        logger.warning(f"Cleanup failed for job {job_id}: {cleanup_error}")
            
            logger.info(f"Launch job {job_id} cancelled")
            return {
                'success': True,
                'message': f'Job {job_id} cancelled successfully'
            }
            
        except Exception as e:
            error_msg = f"Failed to cancel launch: {str(e)}"
            logger.error(error_msg)
            return {
                'success': False,
                'error': error_msg
            }
    
    def get_launch_methods(self) -> Dict[str, Any]:
        """Get available launch methods and their schemas.
        
        Returns:
            Dictionary with launch method schemas
        """
        try:
            from core.launch_schemas import get_all_launch_methods
            methods = get_all_launch_methods()
            
            return {
                'success': True,
                'methods': methods
            }
            
        except Exception as e:
            error_msg = f"Failed to get launch methods: {str(e)}"
            logger.error(error_msg)
            return {
                'success': False,
                'error': error_msg
            }
    
    def get_model_launch_info(self, model_key: str) -> Dict[str, Any]:
        """Get launch information for a specific model.
        
        Args:
            model_key: Model identifier
            
        Returns:
            Dictionary with model launch capabilities
        """
        try:
            model_info = self._registry.get_model_info(model_key)
            if not model_info:
                return {
                    'success': False,
                    'error': f'Model not found: {model_key}'
                }
            
            # Get launch jobs for this model
            launch_jobs = self._db.get_launch_jobs_by_model(model_key)
            
            return {
                'success': True,
                'model_key': model_key,
                'supported_methods': self._registry.get_supported_methods(model_key),
                'supported_engines': self._registry.get_supported_engines(model_key),
                'constraints': self._registry.get_constraints(model_key),
                'launch_jobs': launch_jobs
            }
            
        except Exception as e:
            error_msg = f"Failed to get model launch info: {str(e)}"
            logger.error(error_msg)
            return {
                'success': False,
                'error': error_msg
            }
    
    def poll_job_status(self, job_id: str) -> Dict[str, Any]:
        """Poll external system for job status update.
        
        Args:
            job_id: Job identifier
            
        Returns:
            Dictionary with updated status information
        """
        try:
            job = self._db.get_launch_job(job_id)
            if not job:
                return {
                    'success': False,
                    'error': f'Job not found: {job_id}'
                }
            
            status = job.get('status')
            if status in ['completed', 'failed', 'cancelled']:
                # Job is terminal, no need to poll
                return {
                    'success': True,
                    'status': status,
                    'message': 'Job is in terminal state'
                }
            
            deployment_id = job.get('deployment_id')
            if not deployment_id:
                return {
                    'success': False,
                    'error': 'No deployment ID found for job'
                }
            
            method = job.get('method')
            if method not in self._adapters:
                return {
                    'success': False,
                    'error': f'Unknown method: {method}'
                }
            
            # Poll adapter for status
            adapter = self._adapters[method]
            result = adapter.poll_status(job_id, deployment_id)
            
            return {
                'success': True,
                'status': result.get('status', 'unknown'),
                'endpoint': result.get('endpoint'),
                'error': result.get('error')
            }
            
        except Exception as e:
            error_msg = f"Failed to poll job status: {str(e)}"
            logger.error(error_msg)
            return {
                'success': False,
                'error': error_msg
            }
