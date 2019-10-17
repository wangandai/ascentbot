import boto3
import os
import pickle
import json
from botocore.exceptions import ClientError
from dotenv import load_dotenv
load_dotenv()


def obj_to_json(o):
    try:
        return o.__dict__
    except AttributeError:
        return None


# Monkey patch json.dump and dumps behaviour
class MODJson:
    @staticmethod
    def dump(obj, file, **kwargs):
        return json.dump(obj, file, default=obj_to_json, **kwargs)

    @staticmethod
    def dumps(obj, **kwargs):
        return json.dumps(obj, default=obj_to_json, **kwargs)

    @staticmethod
    def load(f, **kwargs):
        return json.load(f, **kwargs)

    @staticmethod
    def loads(d, **kwargs):
        return json.loads(d, **kwargs)


class Storage:
    def __init__(self, storage_type: str = None):
        storage_inits = {
            "cloudcube": self.__init_cloudcube,
            "local": lambda: None,  # No init required for local storage
        }

        self.SERIALIZERS = {
            "pickle": pickle,
            "json": MODJson,
        }

        self.FILE_MODES = {
            "pickle": "rb+",
            "json": "r+",
        }

        self.save_functions = {
            "cloudcube": self.__save_to_cc,
            "local": self.__save_to_local,
        }

        self.load_functions = {
            "cloudcube": self.__load_from_cc,
            "local": self.__load_from_local,
        }

        # Storage type passed in overrides storage type set by env
        self.storage_type = storage_type or os.getenv("STORAGE", "local")
        storage_inits.get(self.storage_type)()
        print("Storage initialized : connected to {}".format(self.storage_type))

    def __init_cloudcube(self):
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

    def __save_to_local(self, obj, filename, file_type):
        with open(filename, "w+") as f:  # Ensure file exists
            f.write("")
        with open(filename, self.FILE_MODES.get(file_type)) as f:
            self.SERIALIZERS.get(file_type).dump(obj, f)

    def __load_from_local(self, filename, file_type):
        with open(filename, self.FILE_MODES.get(file_type)) as f:
            try:
                return self.SERIALIZERS.get(file_type).load(f)
            except FileNotFoundError:
                return None

    def __save_to_cc(self, obj, filename, file_type):
        d = self.SERIALIZERS.get(file_type).dumps(obj)
        try:
            self.s3.put_object(Bucket=self.CLOUDCUBE_BUCKET,
                               Key="{}{}".format(self.CLOUDCUBE_KEY_PREFIX, filename),
                               Body=d)
        except ClientError as e:
            print(e)
            return False
        return True

    def __load_from_cc(self, filename, file_type):
        try:
            resp = self.s3.get_object(Bucket=self.CLOUDCUBE_BUCKET,
                                      Key="{}{}".format(self.CLOUDCUBE_KEY_PREFIX, filename))

        except ClientError as e:
            print(e)
            return None
        data = resp["Body"].read()
        return self.SERIALIZERS.get(file_type).loads(data)

    def savefile(self, obj, filename, file_type):
        self.save_functions[self.storage_type](obj, filename, file_type)

    def loadfile(self, filename, file_type):
        return self.load_functions[self.storage_type](filename, file_type)
