import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from django.core.management.base import BaseCommand
from django.conf import settings
import requests
import os
import logging
import time
import ssl
from urllib3 import poolmanager
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.auth.transport.requests import Request
from google.auth.exceptions import RefreshError
import json
from requests_oauthlib import OAuth2Session
from http.server import HTTPServer, BaseHTTPRequestHandler
import urllib.parse

class TLSAdapter(requests.adapters.HTTPAdapter):
    def init_poolmanager(self, connections, maxsize, block=False):
        ctx = ssl.create_default_context()
        ctx.set_ciphers('DEFAULT@SECLEVEL=1')
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        ctx.options |= ssl.OP_LEGACY_SERVER_CONNECT
        self.poolmanager = poolmanager.PoolManager(
            num_pools=connections,
            maxsize=maxsize,
            block=block,
            ssl_version=ssl.PROTOCOL_TLSv1_2,
            ssl_context=ctx)

class Command(BaseCommand):
    help = '從指定網站爬取完整公報 PDF 並上傳到 Google Drive 的特定文件夾'

    def add_arguments(self, parser):
        parser.add_argument('--start', type=int, default=1, help='起始期數')

    def handle(self, *args, **options):
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

        creds = self.get_google_drive_creds()
        if not creds:
            self.stdout.write(self.style.ERROR('無法獲取 Google Drive 憑證，上傳功能將被禁用。'))
            return

        drive_service = build('drive', 'v3', credentials=creds)
        self.stdout.write(self.style.SUCCESS('成功獲取 Google Drive 憑證並建立服務。'))

        # 獲取目標文件夾 ID
        target_folder_id = self.get_target_folder_id(drive_service)
        if not target_folder_id:
            self.stdout.write(self.style.ERROR('無法找到目標文件夾，上傳功能將被禁用。'))
            return

        start = options['start']
        issue = start

        pdf_folder = settings.MEDIA_ROOT
        if not os.path.exists(pdf_folder):
            os.makedirs(pdf_folder)

        while True:
            issue_str = f'{issue:02d}'
            url = f'https://ppg.ly.gov.tw/ppg/PublicationBulletinDetail/download/communique1/final/pdf/113/{issue_str}/LCIDC01_113{issue_str}01.pdf'
            file_name = f'第{issue_str}期公報.pdf'
            file_path = os.path.join(pdf_folder, file_name)

            logging.info(f'開始爬取第{issue_str}期公報： {url}')

            if self.download_file(url, file_path):
                self.upload_to_drive(drive_service, file_path, file_name, target_folder_id)
            else:
                logging.info(f'在第{issue_str}期之後沒有找到更多公報。爬取完成。')
                break

            issue += 1

    def download_file(self, file_url, file_path, max_retries=3):
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36'
        }

        session = requests.Session()
        session.mount('https://', TLSAdapter())

        for attempt in range(max_retries):
            try:
                response = session.get(file_url, headers=headers, timeout=30, verify=False)
                response.raise_for_status()

                with open(file_path, 'wb') as f:
                    f.write(response.content)
                logging.info(f'文件 {os.path.basename(file_path)} 已下載到 {file_path}')
                return True

            except requests.RequestException as e:
                logging.error(f'下載 {file_url} 時發生錯：{str(e)}')
                if attempt < max_retries - 1:
                    wait_time = 3 ** attempt  # 指數退避
                    logging.info(f'{wait_time} 秒後重試下載...')
                    time.sleep(wait_time)
                else:
                    logging.error(f'在 {max_retries} 次嘗試後仍無法下載 {file_url}')
                    return False

    def get_google_drive_creds(self):
        client_id = settings.GOOGLE_CLIENT_ID
        client_secret = settings.GOOGLE_CLIENT_SECRET
        redirect_uri = 'http://localhost:8080/'
        scope = ['https://www.googleapis.com/auth/drive.file']
        token_file = 'token.json'

        if os.path.exists(token_file):
            with open(token_file, 'r') as f:
                token_data = json.load(f)
            token_data.update({
                'client_id': client_id,
                'client_secret': client_secret,
            })
            creds = Credentials.from_authorized_user_info(token_data, scope)
            if creds.expired and creds.refresh_token:
                creds.refresh(Request())
                self.save_credentials(creds)
        else:
            flow = OAuth2Session(client_id, scope=scope, redirect_uri=redirect_uri)
            authorization_url, _ = flow.authorization_url(
                "https://accounts.google.com/o/oauth2/auth",
                access_type="offline",
                prompt="select_account"
            )
            print(f'請訪問此 URL 進行授權: {authorization_url}')
            
            # 使用本地伺服器接收重定向
            class OAuthHandler(BaseHTTPRequestHandler):
                def do_GET(self):
                    self.send_response(200)
                    self.send_header('Content-type', 'text/html; charset=utf-8')
                    self.end_headers()
                    self.wfile.write('授權成功，請關閉此窗口並返回命令行。'.encode('utf-8'))
                    self.server.path = self.path

            server = HTTPServer(('localhost', 8080), OAuthHandler)
            print("等待重定向...")
            server.handle_request()
            server.server_close()

            # 解析重定向 URL 中的授權碼
            query = urllib.parse.urlparse(server.path).query
            params = urllib.parse.parse_qs(query)
            code = params['code'][0]

            # 使用授權碼獲取令牌
            token = flow.fetch_token(
                "https://oauth2.googleapis.com/token",
                client_secret=client_secret,
                code=code
            )

            token.update({
                'client_id': client_id,
                'client_secret': client_secret,
            })

            creds = Credentials.from_authorized_user_info(token, scope)
            self.save_credentials(creds)

        return creds

    def save_credentials(self, creds):
        token_data = json.loads(creds.to_json())
        token_data.update({
            'client_id': settings.GOOGLE_CLIENT_ID,
            'client_secret': settings.GOOGLE_CLIENT_SECRET,
        })
        with open('token.json', 'w') as f:
            json.dump(token_data, f)

    def get_target_folder_id(self, drive_service):
        try:
            # 嘗試查找 "立法院公報" 文件夾
            response = drive_service.files().list(
                q="name='立法院公報' and mimeType='application/vnd.google-apps.folder'",
                spaces='drive',
                fields='files(id, name)'
            ).execute()
            
            if not response['files']:
                # 如果找不到，則創建 "立法院公報" 文件夾
                file_metadata = {
                    'name': '立法院公報',
                    'mimeType': 'application/vnd.google-apps.folder'
                }
                file = drive_service.files().create(body=file_metadata, fields='id').execute()
                parent_folder_id = file.get('id')
                logging.info("已創建 '立法院公報' 文件夾")
            else:
                parent_folder_id = response['files'][0]['id']
            
            # 在 "立法院公報" 文件夾中查找或創建 "pdf" 文件夾
            response = drive_service.files().list(
                q=f"name='pdf' and mimeType='application/vnd.google-apps.folder' and '{parent_folder_id}' in parents",
                spaces='drive',
                fields='files(id, name)'
            ).execute()
            
            if not response['files']:
                # 如果找不到，則創建 "pdf" 文件夾
                file_metadata = {
                    'name': 'pdf',
                    'parents': [parent_folder_id],
                    'mimeType': 'application/vnd.google-apps.folder'
                }
                file = drive_service.files().create(body=file_metadata, fields='id').execute()
                pdf_folder_id = file.get('id')
                logging.info("已在 '立法院公報' 文件夾中創建 'pdf' 文件夾")
            else:
                pdf_folder_id = response['files'][0]['id']
            
            return pdf_folder_id
        except HttpError as error:
            logging.error(f"獲取或創建目標文件夾時發生 HTTP 錯誤：{error}")
            return None
        except Exception as e:
            logging.error(f"獲取或創建目標文件夾時發生錯誤：{str(e)}")
            return None

    def upload_to_drive(self, drive_service, file_path, file_name, folder_id):
        if not drive_service or not folder_id:
            logging.warning(f"Google Drive 服務未初始化或找不到目標文件夾，跳過上傳 {file_name}")
            return
        
        file_metadata = {
            'name': file_name,
            'parents': [folder_id]
        }
        media = MediaFileUpload(file_path, resumable=True)
        try:
            file = drive_service.files().create(body=file_metadata, media_body=media, fields='id').execute()
            logging.info(f'文件 {file_name} 已上傳到 Google Drive 的指定文件夾，文件 ID: {file.get("id")}')
        except Exception as e:
            logging.error(f'上傳 {file_name} 到 Google Drive 時發生錯誤：{str(e)}')

# 使用方法: python manage.py gazette [--start START_ISSUE]