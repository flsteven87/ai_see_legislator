from django.core.management.base import BaseCommand
from django.conf import settings
import os
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
import io
import json
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

class Command(BaseCommand):
    help = '從 Google Drive 下載立法院公報 MD 文件'

    def handle(self, *args, **options):
        creds = self.get_google_drive_creds()
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    'credentials.json',
                    ['https://www.googleapis.com/auth/drive.readonly'],
                    redirect_uri='http://localhost:8080/'
                )
                creds = flow.run_local_server(port=8080)

            # 保存憑證以供下次使用
            with open('token.json', 'w') as token:
                token.write(creds.to_json())

        if not creds:
            self.stdout.write(self.style.ERROR('無法獲取 Google Drive 憑證，下載功能將被禁用。'))
            return

        drive_service = build('drive', 'v3', credentials=creds)
        self.stdout.write(self.style.SUCCESS('成功獲取 Google Drive 憑證並建立服務。'))

        # 獲取目標文件夾 ID
        folder_id = self.get_target_folder_id(drive_service)
        if not folder_id:
            self.stdout.write(self.style.ERROR('無法找到目標文件夾，下載功能將被禁用。'))
            return

        self.download_files(drive_service, folder_id, '')

    def get_google_drive_creds(self):
        token_file = 'token.json'
        if os.path.exists(token_file):
            with open(token_file, 'r') as f:
                token_data = json.load(f)
            creds = Credentials.from_authorized_user_info(token_data, ['https://www.googleapis.com/auth/drive.readonly'])
            return creds
        else:
            self.stdout.write(self.style.WARNING('找不到 token.json 檔案，將進行重新授權。'))
            return None

    def get_target_folder_id(self, drive_service):
        try:
            results = drive_service.files().list(
                q="mimeType='application/vnd.google-apps.folder'",
                spaces='drive',
                fields='nextPageToken, files(id, name)'
            ).execute()
            items = results.get('files', [])

            if not items:
                self.stdout.write(self.style.WARNING('未找到任何文件夾。'))
                return None

            self.stdout.write(self.style.SUCCESS('找到以下文件夾：'))
            target_folder_id = None
            for item in items:
                self.stdout.write(f"文件夾名稱: {item['name']}, ID: {item['id']}")
                if item['name'] == '立法院公報':
                    target_folder_id = item['id']

            if target_folder_id:
                self.stdout.write(self.style.SUCCESS(f"找到目標文件夾 '立法院公報'，ID: {target_folder_id}"))
                
                # 在 '立法院公報' 文件夾中查找 'md' 子文件夾
                sub_results = drive_service.files().list(
                    q=f"'{target_folder_id}' in parents and mimeType='application/vnd.google-apps.folder' and name='md'",
                    spaces='drive',
                    fields='files(id, name)'
                ).execute()
                sub_items = sub_results.get('files', [])
                
                if sub_items:
                    md_folder_id = sub_items[0]['id']
                    self.stdout.write(self.style.SUCCESS(f"找到 'md' 子文件夾，ID: {md_folder_id}"))
                    return md_folder_id
                else:
                    self.stdout.write(self.style.WARNING("在 '立法院公報' 文件夾中未找到 'md' 子文件夾"))
                    return target_folder_id
            else:
                self.stdout.write(self.style.WARNING("未找到 '立法院公報' 文件夾"))
                return None

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'獲取文件夾列表時發生錯誤：{str(e)}'))
            return None

    def download_files(self, drive_service, folder_id, current_path):
        try:
            results = drive_service.files().list(
                q=f"'{folder_id}' in parents",
                spaces='drive',
                fields="nextPageToken, files(id, name, mimeType)"
            ).execute()
            items = results.get('files', [])

            if not items:
                self.stdout.write(self.style.WARNING(f'文件夾 {current_path} 中未找到文件。'))
                return

            for item in items:
                file_id = item['id']
                file_name = item['name']
                mime_type = item['mimeType']
                
                new_path = os.path.join(current_path, file_name)
                
                if mime_type == 'application/vnd.google-apps.folder':
                    self.stdout.write(f"處理子文件夾: {new_path}")
                    new_folder_path = os.path.join(settings.BASE_DIR, 'data', 'md', new_path)
                    if not os.path.exists(new_folder_path):
                        os.makedirs(new_folder_path)
                    self.download_files(drive_service, file_id, new_path)
                else:
                    self.download_file(drive_service, file_id, file_name, new_path)

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'下載文件時發生錯誤：{str(e)}'))

    def download_file(self, drive_service, file_id, file_name, file_path):
        try:
            request = drive_service.files().get_media(fileId=file_id)
            file_path = os.path.join(settings.BASE_DIR, 'data', 'md', file_path)
            
            with io.FileIO(file_path, 'wb') as fh:
                downloader = MediaIoBaseDownload(fh, request)
                done = False
                while done is False:
                    status, done = downloader.next_chunk()
                    self.stdout.write(f'下載 {file_name} {int(status.progress() * 100)}%.')
            
            self.stdout.write(self.style.SUCCESS(f'文件 {file_name} 已下載到 {file_path}'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'下載文件 {file_name} 時發生錯誤：{str(e)}'))

# 使用方法：python manage.py download_from_google_drive