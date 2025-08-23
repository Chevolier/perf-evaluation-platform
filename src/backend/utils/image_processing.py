"""Image and video processing utilities."""

import base64
import io
import tempfile
import subprocess
from typing import List, Optional, Tuple
from pathlib import Path
from PIL import Image


def encode_image(image_path: str) -> Optional[str]:
    """Encode image file to base64 string.
    
    Args:
        image_path: Path to the image file
        
    Returns:
        Base64 encoded image string or None if error
    """
    try:
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode("utf-8")
    except Exception as e:
        print(f"Error encoding image {image_path}: {e}")
        return None


def encode_image_for_emd(image_base64: str) -> str:
    """Prepare base64 image for EMD API format.
    
    Args:
        image_base64: Base64 encoded image
        
    Returns:
        Formatted image data for EMD
    """
    return f"data:image/jpeg;base64,{image_base64}"


def extract_frames_from_video(video_base64: str, num_frames: int = 8) -> List[str]:
    """Extract frames from base64 encoded video.
    
    Args:
        video_base64: Base64 encoded video
        num_frames: Number of frames to extract
        
    Returns:
        List of base64 encoded frame images
    """
    try:
        # Decode video data
        video_data = base64.b64decode(video_base64)
        
        # Create temporary files
        with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as video_temp:
            video_temp.write(video_data)
            video_temp_path = video_temp.name
        
        # Create temporary directory for frames
        frames_dir = tempfile.mkdtemp()
        frames_pattern = Path(frames_dir) / "frame_%03d.jpg"
        
        # Extract frames using ffmpeg
        ffmpeg_cmd = [
            'ffmpeg',
            '-i', video_temp_path,
            '-vf', f'select=not(mod(n\\,{max(1, int(30/num_frames))})),scale=512:512',
            '-vsync', 'vfr',
            '-frames:v', str(num_frames),
            '-q:v', '2',
            str(frames_pattern)
        ]
        
        result = subprocess.run(
            ffmpeg_cmd,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode != 0:
            print(f"FFmpeg error: {result.stderr}")
            return []
        
        # Read and encode frames
        frames = []
        for i in range(1, num_frames + 1):
            frame_path = Path(frames_dir) / f"frame_{i:03d}.jpg"
            if frame_path.exists():
                with open(frame_path, 'rb') as f:
                    frame_data = base64.b64encode(f.read()).decode('utf-8')
                    frames.append(frame_data)
        
        # Cleanup temporary files
        Path(video_temp_path).unlink(missing_ok=True)
        for frame_file in Path(frames_dir).glob("*.jpg"):
            frame_file.unlink()
        Path(frames_dir).rmdir()
        
        return frames
        
    except subprocess.TimeoutExpired:
        print("Video processing timed out")
        return []
    except Exception as e:
        print(f"Error extracting frames: {e}")
        return []


def resize_image(image_base64: str, max_size: Tuple[int, int] = (1024, 1024)) -> str:
    """Resize image while maintaining aspect ratio.
    
    Args:
        image_base64: Base64 encoded image
        max_size: Maximum dimensions (width, height)
        
    Returns:
        Base64 encoded resized image
    """
    try:
        # Decode image
        image_data = base64.b64decode(image_base64)
        image = Image.open(io.BytesIO(image_data))
        
        # Calculate new size maintaining aspect ratio
        image.thumbnail(max_size, Image.Resampling.LANCZOS)
        
        # Save resized image to bytes
        output_buffer = io.BytesIO()
        image_format = image.format if image.format else 'JPEG'
        image.save(output_buffer, format=image_format, quality=85)
        
        # Encode back to base64
        resized_data = base64.b64encode(output_buffer.getvalue()).decode('utf-8')
        return resized_data
        
    except Exception as e:
        print(f"Error resizing image: {e}")
        return image_base64  # Return original if resize fails


def validate_image_format(image_base64: str) -> bool:
    """Validate if the base64 string represents a valid image.
    
    Args:
        image_base64: Base64 encoded image
        
    Returns:
        True if valid image format
    """
    try:
        image_data = base64.b64decode(image_base64)
        image = Image.open(io.BytesIO(image_data))
        # Try to load the image to verify it's valid
        image.load()
        return True
    except Exception:
        return False


def get_image_info(image_base64: str) -> dict:
    """Get information about an image.
    
    Args:
        image_base64: Base64 encoded image
        
    Returns:
        Dictionary with image information
    """
    try:
        image_data = base64.b64decode(image_base64)
        image = Image.open(io.BytesIO(image_data))
        
        return {
            "format": image.format,
            "mode": image.mode,
            "size": image.size,
            "width": image.width,
            "height": image.height,
            "has_transparency": image.mode in ('RGBA', 'LA', 'P'),
            "file_size_bytes": len(image_data)
        }
    except Exception as e:
        return {"error": str(e)}


def enhance_prompt_for_video(original_prompt: str, num_frames: int) -> str:
    """Enhance prompt for video analysis.
    
    Args:
        original_prompt: Original text prompt
        num_frames: Number of video frames
        
    Returns:
        Enhanced prompt for video analysis
    """
    if num_frames <= 1:
        return original_prompt
    
    video_context = f"""
You are viewing a video sequence with {num_frames} frames. Please analyze the video content considering:
1. The temporal sequence and any changes between frames
2. Overall scene understanding and context
3. Any motion, actions, or transitions occurring

Original request: {original_prompt}

Please provide a comprehensive analysis of the video content.
"""
    return video_context.strip()