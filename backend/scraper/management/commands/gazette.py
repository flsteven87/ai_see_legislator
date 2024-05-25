from django.core.management.base import BaseCommand
import requests
from bs4 import BeautifulSoup
import os
from django.conf import settings

class Command(BaseCommand):

    def handle(self, *args, **options):

        for i in range(1, 39):
            # 如果 i 為個位數，則在前面補 0
            if i < 10:
                i = f'0{i}'
            # create folder for 每期公報 
            folder_path = os.path.join(settings.MEDIA_ROOT, f'第{i}期')
            if not os.path.exists(folder_path):
                os.mkdir(folder_path)
            url = f'https://ppg.ly.gov.tw/ppg/publications/official-gazettes/113/{i}/01/details'
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36'
            }
            self.stdout.write(self.style.SUCCESS(f'Starting to scrape 第{i}期公報： {url}'))
            self.scrape_gazette(url, folder_path, headers=headers)
        
    def scrape_gazette(self, url, folder_path, headers=None):
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            links = soup.find_all('a', title="doc下載(另開視窗)")

            for link in links:
                file_url = link.get('href')
                if file_url:
                    # 獲取文件名
                    file_name = file_url.split('/')[-1]
                    # 下載文件
                    file_response = requests.get(file_url, headers=headers)
                    file_path = os.path.join(folder_path, file_name)
                    with open(file_path, 'wb') as f:
                        f.write(file_response.content)
                    print(f'File {file_name} downloaded to {file_path}')        
        else:
            self.stdout.write(self.style.ERROR(f'Failed to scrape {url}'))
            self.stdout.write(self.style.ERROR(f'Status code: {response.status_code}'))                          
