import os
from io import BytesIO
from PIL import Image
from functools import lru_cache
from dotenv import load_dotenv, find_dotenv

import firebase_admin
from firebase_admin import firestore

from gcloud import storage
from oauth2client.service_account import ServiceAccountCredentials

#LOAD ENV
load_dotenv()

#storage
class Bucket():
    def __init__(self):
        self.base_storage = os.getenv("FB_STORAGE_URL")
        scopes = [
                'https://www.googleapis.com/auth/firebase.database',
                'https://www.googleapis.com/auth/userinfo.email',
                "https://www.googleapis.com/auth/cloud-platform"
            ]
        self.credentials = ServiceAccountCredentials.from_json_keyfile_name(os.getenv("GOOGLE_APPLICATION_CREDENTIALS"), scopes)
        self.url = f"https://firebasestorage.googleapis.com/v0/b/{self.base_storage}"
        self.client = storage.Client(credentials=self.credentials, project=self.base_storage)
        self.bucket = self.client.get_bucket(self.base_storage)

    def put(self, 
        image:Image, 
        owner_uuid:str, 
        job_uuid:str
    ):
        path = f'{owner_uuid}/images/{job_uuid}/{job_uuid}.jpg'
        blob = self.bucket.blob(path)
        blob.upload_from_string(self.get_bytes_value(image), content_type="image/jpeg")

    def get_bytes_value(self, 
        image:Image
    ):
        img_byte_arr = BytesIO()
        image.save(img_byte_arr, format='JPEG')
        return img_byte_arr.getvalue()

    def download(self,
        owner_uuid:str, 
        job_uuid:str,
        topil=False,
    ):
        blob = self.bucket.get_blob(f'{owner_uuid}/images/{job_uuid}/{job_uuid}.jpg')
        asset = blob.download_as_string()
        
        if topil: return self.bytes2pil(asset)

        return asset
    
    def bytes2pil(self, bytes):
        img = BytesIO(bytes)
        return Image.open(img)


class BackendFirebase:
    def __init__(self):
        default_fb_app = firebase_admin.initialize_app()
        self.db = firestore.client()
        self.db_users = self.db.collection('users')
        self.db_jobs = self.db.collection('jobs')
        self.db_bm = self.db.collection('basemodels')
        self.bucket = Bucket()

    def get_credits(self, user):
        try:
            credits = user['credits']
        except:
            credits = 0
            
        # try:
        #     credits_on_hold = user['credits_on_hold']
        # except:
        #     credits_on_hold = 0
            
        return credits

    def verify_user_credit(self, uid):
        ref = self.db_users.document(uid)
        user = ref.get().to_dict()
        
        #CHECK USER EXISTS
        users = [e.id for e in self.db_users.list_documents()]
        if not uid in users:
            return 403, "Unknown user"

        #GET CREDITS AND CREDITS_ON_HOLD
        credits = self.get_credits(user)
        
        #RAISE IF CREDITS LESS THAN 0
        if credits <= 0:
            return 403, "Insufficient credits"
        
        return 200, credits

    def remove_credit(self, uid): 
        ref = self.db_users.document(uid)
        credits = ref.get().to_dict()['credits']
        #MOVE A CREDIT FROM CREDIT TO ON_HOLD_CREDIT
        try:
            new_credits = credits - 1
            ref.update({'credits': new_credits})
        
            return 200, None

        except:
            return 500, "Internal server error" 

    def set_job(self, params):
        job_uuid = params.pop('job_uuid')
        ref = self.db_jobs.document(job_uuid)
        ref.set(params)
        return ref.get().to_dict()

    def update_job(self, job_uuid, update_dict):
        ref = self.db_jobs.document(job_uuid)
        ref.update(update_dict)
        return ref.get().to_dict()
    
    def get_job(self, job_uuid):
        ref = self.db_jobs.document(job_uuid)
        return ref.get().to_dict()
    
    def get_job_by_owner(self, owner_uuid):
        return [{e.id: e.to_dict()} for e in self.db_jobs.where('owner_uuid', '==', owner_uuid).stream()]

    def delete_app(self):
        firebase_admin.delete_app(firebase_admin.get_app())
    
    def get_bm(self):
        refs = self.db_bm.get()
        return {ref.id: ref.to_dict()for ref in refs}