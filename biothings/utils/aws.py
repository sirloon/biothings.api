import os
import logging
from urllib.parse import urlparse
import mimetypes

from boto import connect_s3, s3 as botos3
import boto3
import botocore.exceptions

try:
    from biothings import config
except ImportError:
    # assuming key, secret and bucket will be passed
    # to all functions
    pass


def key_exists(bucket, s3key, aws_key=None, aws_secret=None):
    client = boto3.client("s3",aws_access_key_id=aws_key,aws_secret_access_key=aws_secret)
    try:
        client.head_object(Bucket=bucket,Key=s3key)
        return True
    except Exception as e:
        if e.response["Error"]["Code"] == "404":
            return False
        else:
            raise


def send_s3_file(localfile, s3key, overwrite=False, permissions=None, metadata=None,
                 content=None, content_type=None, aws_key=None, aws_secret=None, s3_bucket=None):
    '''save a localfile to s3 bucket with the given key.
       bucket is set via S3_BUCKET
       it also save localfile's lastmodified time in s3 file's metadata
    '''
    metadata = metadata or {}
    try:
        aws_key = aws_key or getattr(config, "AWS_SECRET")
        aws_secret = aws_secret or getattr(config, "AWS_SECRET")
        s3_bucket = s3_bucket or getattr(config, "S3_BUCKET")
    except AttributeError:
        logging.info("Skip sending file to S3, missing information in config file: AWS_KEY, AWS_SECRET or S3_BUCKET")
        return
    s3 = connect_s3(aws_key, aws_secret)
    bucket = s3.get_bucket(s3_bucket)
    bucket_location = bucket.get_location()
    k = bucket.new_key(s3key)
    if not overwrite:
        assert not k.exists(), 's3key "{}" already exists.'.format(s3key)
    for header in metadata:
        k.set_metadata(header, metadata[header])
    if content_type:
        k.content_type = content_type
    if content:
        k.set_contents_from_string(content)
    else:
        assert os.path.exists(localfile), 'localfile "{}" does not exist.'.format(localfile)
        lastmodified = os.stat(localfile)[-2]
        k.set_metadata('lastmodified', lastmodified)
        k.set_contents_from_filename(localfile)
    if permissions:
        k.set_acl(permissions)


def send_s3_big_file(localfile, s3key, overwrite=False, acl=None,
                     aws_key=None, aws_secret=None, s3_bucket=None,
                     storage_class=None):
    """
    Multiparts upload for file bigger than 5GiB
    """
    # TODO: maybe merge with send_s3_file() based in file size ? It would need boto3 migration
    try:
        aws_key = aws_key or getattr(config, "AWS_SECRET")
        aws_secret = aws_secret or getattr(config, "AWS_SECRET")
        s3_bucket = s3_bucket or getattr(config, "S3_BUCKET")
    except AttributeError:
        logging.info("Skip sending file to S3, missing information in config file: AWS_KEY, AWS_SECRET or S3_BUCKET")
        return
    client = boto3.client("s3",aws_access_key_id=aws_key,aws_secret_access_key=aws_secret)
    if not overwrite and key_exists(s3_bucket,s3key,aws_key,aws_secret):
        raise Exception("Key '%s' already exist" % s3key)
    config = boto3.s3.transfer.TransferConfig(multipart_threshold=1024 * 25, max_concurrency=10,
                            multipart_chunksize=1024 * 25, use_threads=True)
    extra = {"ACL" : acl or "private",
             "ContentType" : mimetypes.MimeTypes().guess_type(localfile)[0] or "binary/octet-stream",
             "StorageClass" : storage_class or "REDUCED_REDUNDANCY"
            }
    client.upload_file(Filename=localfile,Bucket=s3_bucket,Key=s3key,ExtraArgs=extra,Config=config)


def get_s3_file(s3key, localfile=None, return_what=False,
                aws_key=None, aws_secret=None, s3_bucket=None):
    aws_key = aws_key or getattr(config, "AWS_SECRET")
    aws_secret = aws_secret or getattr(config, "AWS_SECRET")
    s3_bucket = s3_bucket or getattr(config, "S3_BUCKET")
    localfile = localfile or os.path.basename(s3key)
    s3 = connect_s3(aws_key, aws_secret)
    bucket = s3.get_bucket(s3_bucket)
    k = bucket.get_key(s3key)
    if not k:
        raise FileNotFoundError(s3key)
    if return_what == "content":
        return k.get_contents_as_string()
    elif return_what == "key":
        return k
    else:
        k.get_contents_to_filename(localfile)


def get_s3_folder(s3folder, basedir=None, aws_key=None, aws_secret=None, s3_bucket=None):
    aws_key = aws_key or getattr(config, "AWS_SECRET")
    aws_secret = aws_secret or getattr(config, "AWS_SECRET")
    s3_bucket = s3_bucket or getattr(config, "S3_BUCKET")
    s3 = connect_s3(aws_key, aws_secret)
    bucket = s3.get_bucket(s3_bucket)
    cwd = os.getcwd()
    try:
        if basedir:
            os.chdir(basedir)
        if not os.path.exists(s3folder):
            os.makedirs(s3folder)
        for k in bucket.list(s3folder):
            get_s3_file(k.key, localfile=k.key, aws_key=aws_key, aws_secret=aws_secret, s3_bucket=s3_bucket)
    finally:
        os.chdir(cwd)


def send_s3_folder(folder, s3basedir=None, acl=None, overwrite=False,
                   aws_key=None, aws_secret=None, s3_bucket=None):
    aws_key = aws_key or getattr(config, "AWS_SECRET")
    aws_secret = aws_secret or getattr(config, "AWS_SECRET")
    s3_bucket = s3_bucket or getattr(config, "S3_BUCKET")
    s3 = connect_s3(aws_key, aws_secret)
    s3.get_bucket(s3_bucket)    # check if s3_bucket exists
    cwd = os.getcwd()
    if not s3basedir:
        s3basedir = os.path.basename(cwd)
    for localf in [f for f in os.listdir(folder) if not f.startswith(".")]:
        fullpath = os.path.join(folder, localf)
        if os.path.isdir(fullpath):
            send_s3_folder(fullpath, os.path.join(s3basedir, localf),
                           overwrite=overwrite, acl=acl,
                           aws_key=aws_key, aws_secret=aws_secret, s3_bucket=s3_bucket)
        else:
            send_s3_big_file(fullpath, os.path.join(s3basedir, localf),
                             overwrite=overwrite, acl=acl,
                             aws_key=aws_key, aws_secret=aws_secret, s3_bucket=s3_bucket)


def get_s3_url(s3key, aws_key=None, aws_secret=None, s3_bucket=None):
    try:
        k = get_s3_file(s3key, return_what="key",
                        aws_key=aws_key, aws_secret=aws_secret, s3_bucket=s3_bucket)
    except FileNotFoundError:
        return None
    # generate_url will include some acdesskey, signature, etc... we want to remove this
    # as the bucket is public anyway and want "clean" url
    url = k.generate_url(expires_in=0) # never (and whatever, we
    return urlparse(url)._replace(query="").geturl()


def create_bucket(name, region=None, aws_key=None, aws_secret=None, acl=None,
                  ignore_already_exists=False):
    """Create a S3 bucket "name" in optional "region". If aws_key and aws_secret
    are set, S3 client will these, otherwise it'll use default system-wide setting.
    "acl" defines permissions on the bucket: "private" (default), "public-read",
    "public-read-write" and "authenticated-read"
    """
    client = boto3.client("s3",aws_access_key_id=aws_key,aws_secret_access_key=aws_secret)
    acl = acl or "private"
    kwargs = {"ACL" : acl, "Bucket" : name}
    if region:
        kwargs["CreateBucketConfiguration"] = {"LocationConstraint" : region}
    try:
        client.create_bucket(**kwargs)
    except botocore.exceptions.ClientError as e:
        if e.response["Error"]["Code"] == "BucketAlreadyOwnedByYou" and not ignore_already_exists:
            raise

def set_static_website(name, aws_key=None, aws_secret=None, index="index.html", error="error.html"):
    client = boto3.client("s3",aws_access_key_id=aws_key,aws_secret_access_key=aws_secret)
    conf = {'IndexDocument': {'Suffix': index},
            'ErrorDocument': {'Key': error}}
    client.put_bucket_website(Bucket=name,WebsiteConfiguration=conf)
    location = client.get_bucket_location(Bucket=name)
    region = location["LocationConstraint"]
    # generate website URL
    return "http://%(name)s.s3-website-%(region)s.amazonaws.com" % {"name":name,"region":region}

