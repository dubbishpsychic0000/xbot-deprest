import os
import httpx
from typing import List, Optional
from pathlib import Path
from config import logger

class MediaHandler:
    def __init__(self, download_dir: str = "media"):
        self.download_dir = Path(download_dir)
        self.download_dir.mkdir(exist_ok=True)
        self.supported_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.mp4', '.mov'}
    
    async def download_media(self, url: str, filename: Optional[str] = None) -> Optional[str]:
        """Download media from URL and return local path"""
        try:
            if not filename:
                filename = url.split('/')[-1].split('?')[0]
            
            file_ext = Path(filename).suffix.lower()
            if file_ext not in self.supported_extensions:
                logger.warning(f"Unsupported file type: {file_ext}")
                return None
            
            file_path = self.download_dir / filename
            
            if file_path.exists():
                logger.info(f"Media already exists: {file_path}")
                return str(file_path)
            
            async with httpx.AsyncClient() as client:
                response = await client.get(url, timeout=30)
                response.raise_for_status()
                
                with open(file_path, 'wb') as f:
                    f.write(response.content)
                
                logger.info(f"Downloaded media: {file_path}")
                return str(file_path)
        
        except Exception as e:
            logger.error(f"Failed to download media from {url}: {e}")
            return None
    
    async def download_tweet_media(self, tweet_data: dict) -> List[str]:
        """Download all media from a tweet"""
        media_paths = []
        
        if 'media' in tweet_data and tweet_data['media']:
            for i, media_url in enumerate(tweet_data['media']):
                filename = f"tweet_{tweet_data['id']}_media_{i}.{media_url.split('.')[-1]}"
                path = await self.download_media(media_url, filename)
                if path:
                    media_paths.append(path)
        
        return media_paths
    
    def cleanup_old_media(self, days: int = 7):
        """Remove media files older than specified days"""
        import time
        current_time = time.time()
        cutoff_time = current_time - (days * 24 * 60 * 60)
        
        removed_count = 0
        for file_path in self.download_dir.iterdir():
            if file_path.is_file() and file_path.stat().st_mtime < cutoff_time:
                try:
                    file_path.unlink()
                    removed_count += 1
                except Exception as e:
                    logger.error(f"Failed to remove old media {file_path}: {e}")
        
        if removed_count > 0:
            logger.info(f"Cleaned up {removed_count} old media files")
    
    def get_media_info(self, file_path: str) -> dict:
        """Get basic info about media file"""
        path = Path(file_path)
        if not path.exists():
            return {}
        
        stat = path.stat()
        return {
            'filename': path.name,
            'size': stat.st_size,
            'extension': path.suffix.lower(),
            'is_image': path.suffix.lower() in {'.jpg', '.jpeg', '.png', '.gif'},
            'is_video': path.suffix.lower() in {'.mp4', '.mov'}
        }

async def process_tweet_media(tweet_data: dict) -> List[str]:
    """Main function to process media from tweet data"""
    handler = MediaHandler()
    return await handler.download_tweet_media(tweet_data)

if __name__ == "__main__":
    import asyncio
    
    async def test():
        test_tweet = {
            'id': '12345',
            'media': ['https://example.com/image.jpg']
        }
        paths = await process_tweet_media(test_tweet)
        print(f"Downloaded media: {paths}")
    
    asyncio.run(test())
    