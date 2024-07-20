from django.core.management.base import BaseCommand
import requests
from bs4 import BeautifulSoup
import os
from django.conf import settings
import logging
import time

class Command(BaseCommand):
    help = 'Scrape gazette PDFs from the specified website'

    def add_arguments(self, parser):
        parser.add_argument('--start', type=int, default=1, help='Start issue number')

    def handle(self, *args, **options):
        # 設置日誌
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

        start = options['start']
        issue = start

        while True:
            issue_str = f'{issue:02d}'  # 確保 issue 為兩位數字串
            folder_path = os.path.join(settings.MEDIA_ROOT, f'第{issue_str}期')
            if not os.path.exists(folder_path):
                os.makedirs(folder_path)
            
            url = f'https://ppg.ly.gov.tw/ppg/publications/official-gazettes/113/{issue_str}/01/details'
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36'
            }
            logging.info(f'Starting to scrape 第{issue_str}期公報： {url}')
            
            if not self.scrape_gazette(url, folder_path, headers=headers):
                logging.info(f'No more gazettes found after 第{issue_str}期. Scraping completed.')
                break

            issue += 1

    def scrape_gazette(self, url, folder_path, headers=None, max_retries=5):
        for attempt in range(max_retries):
            try:
                response = requests.get(url, headers=headers, timeout=50)
                response.raise_for_status()
                
                soup = BeautifulSoup(response.content, 'html.parser')
                links = soup.find_all('a', title="pdf下載(另開視窗)")

                if not links:
                    return False  # 如果沒有找到下載鏈接，返回 False

                for link in links:
                    file_url = link.get('href')
                    if file_url:
                        file_name = file_url.split('/')[-1]
                        file_path = os.path.join(folder_path, file_name)
                        
                        # 檢查文件是否已存在
                        if os.path.exists(file_path):
                            logging.info(f'File {file_name} already exists, skipping download')
                            continue

                        self.download_file(file_url, file_path, headers)
                
                return True  # 成功爬取，返回 True
            
            except requests.RequestException as e:
                logging.error(f'Error occurred while scraping {url}: {str(e)}')
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt  # 指數退避
                    logging.info(f'Retrying in {wait_time} seconds...')
                    time.sleep(wait_time)
                else:
                    logging.error(f'Failed to scrape {url} after {max_retries} attempts')
                    return False

    def download_file(self, file_url, file_path, headers, max_retries=3):
        for attempt in range(max_retries):
            try:
                file_response = requests.get(file_url, headers=headers, timeout=30)
                file_response.raise_for_status()
                
                with open(file_path, 'wb') as f:
                    f.write(file_response.content)
                logging.info(f'File {os.path.basename(file_path)} downloaded to {file_path}')
                break  # 如果成功，跳出重試循環
            
            except requests.RequestException as e:
                logging.error(f'Error occurred while downloading {file_url}: {str(e)}')
                if attempt < max_retries - 1:
                    wait_time = 3 ** attempt  # 指數退避
                    logging.info(f'Retrying download in {wait_time} seconds...')
                    time.sleep(wait_time)
                else:
                    logging.error(f'Failed to download {file_url} after {max_retries} attempts')

# 使用方法: python manage.py gazette [--start START_ISSUE]