import boto3
import os
import pickle
from botocore.exceptions import ClientError
from dotenv import load_dotenv
load_dotenv()

CLOUDCUBE = "cloudcube"


class Storage:
    def __init__(self):
        if os.getenv("STORAGE") == CLOUDCUBE:
            self.CLOUDCUBE_ACCESS_KEY_ID = os.getenv("CLOUDCUBE_ACCESS_KEY_ID")
            self.CLOUDCUBE_SECRET_ACCESS_KEY = os.getenv("CLOUDCUBE_SECRET_ACCESS_KEY")
            self.CLOUDCUBE_URL = os.getenv("CLOUDCUBE_URL")
            self.CLOUDCUBE_BUCKET = os.getenv("CLOUDCUBE_BUCKET")
            self.CLOUDCUBE_KEY_PREFIX = os.getenv("CLOUDCUBE_KEY_PREFIX")
            self.s3 = boto3.client(
                's3',
                aws_access_key_id=self.CLOUDCUBE_ACCESS_KEY_ID,
                aws_secret_access_key=self.CLOUDCUBE_SECRET_ACCESS_KEY,
            )

    def __save_to_local(self, obj, filename):
        with open(filename, "wb") as f:
            pickle.dump(obj, f)

    def __load_from_local(self, filename):
        with open(filename, "rb") as f:
            try:
                return pickle.load(f)
            except FileNotFoundError:
                return None

    def __save_to_cc(self, obj, filename):
        d = pickle.dumps(obj)
        try:
            self.s3.put_object(Bucket=self.CLOUDCUBE_BUCKET,
                               Key="{}{}".format(self.CLOUDCUBE_KEY_PREFIX, filename),
                               Body=d)
        except ClientError as e:
            print(e)
            return False
        return True

    def __load_from_cc(self, filename):
        try:
            resp = self.s3.get_object(Bucket=self.CLOUDCUBE_BUCKET,
                                      Key="{}{}".format(self.CLOUDCUBE_KEY_PREFIX, filename))

        except ClientError as e:
            print(e)
            return None
        return pickle.loads(resp["Body"].read())

    def savefile(self, obj, filename):
        if os.getenv("STORAGE") == CLOUDCUBE:
            __save = self.__save_to_cc
        else:
            __save = self.__save_to_local
        __save(obj, filename)

    def loadfile(self, filename):
        if os.getenv("STORAGE") == CLOUDCUBE:
            __load = self.__load_from_cc
        else:
            __load = self.__load_from_local
        return __load(filename)
