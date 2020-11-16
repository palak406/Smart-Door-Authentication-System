import boto3
import base64
import cv2
import json
import datetime
import random

bucketName = "owner-photos"
collection_id = "collection1"

ownerPhoneNumber = "9294149886"

def parse_face_search_response(faceSearchResponse):
    matched = 0
    faceId = ""
    if len(faceSearchResponse) > 0:
        if faceSearchResponse[0]["MatchedFaces"]:
            matched = 1
            faceId = faceSearchResponse[0]["MatchedFaces"][-1]["Face"]["FaceId"]
    else:
        matched = -1
    return matched, faceId

def get_face_details(faceId):
    print("Dynamo DB")
    faceDetails = None
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table('visitors')
    response = table.get_item(Key={'faceId' : faceId})
    try:
        faceDetails = response["Item"] # parse and store only relevant info
    except:
        print("Debug Error: Face Id does not match to one in DynamoDb")
        print("FaceId is ",faceId)
    return faceDetails
    
def parse_phone_number(faceDetails):
    phoneNumber = faceDetails["phoneNumber"]
    if "+1" not in phoneNumber:
        phoneNumber  = '+1'+phoneNumber
    return phoneNumber

def check_otp_existence(faceId):
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table('passcodes')
    response = table.get_item(Key={'faceId': faceId})
    otp_current_sent = 0
    #print(response)
    if response.get("Item", None):
        return True
    else:
        return False
    
def generate_store_send_otp(faceId, phoneNumber):
    otp = random.randint(100000,999999) #TODO: Randomize OTP
    expiration_time = 300
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table('passcodes')
    response = table.get_item(Key={'faceId': faceId})
    #print(response)
    if response.get("Item", None):
        print("OTP already sent")
    else:
        print("Generating OTP and storing to passcodes table")
        response = table.put_item(
                Item={
                        'createdAtTimestamp': str(datetime.datetime.now()),
                        'ttl': int(datetime.datetime.now().timestamp() + expiration_time),
                        'OTP': otp,
                        'faceId': faceId
                    }
                )
        msg = "OTP for access is " + str(otp)
        send_message(phoneNumber, msg)

def send_message(phoneNumber, msg):
    client = boto3.client('sns')
    if "+1" not in phoneNumber:
        phoneNumber  = '+1'+phoneNumber
    print("Sending SMS to " + phoneNumber + " : " + msg)
    response = client.publish(PhoneNumber=phoneNumber, Message=msg)

def collection_insert(image):
    client = boto3.client('rekognition')
    print("Adding " + image + " from bucket [" + bucketName + "] to collection[" + collection_id + "]")
    response = client.index_faces(CollectionId=collection_id,
                                    Image={'S3Object':{'Bucket':bucketName,'Name':image}},
                                    ExternalImageId=image,
                                    MaxFaces=1,
                                    QualityFilter="AUTO",
                                    DetectionAttributes=['ALL'])
    faceId = response['FaceRecords'][0]['Face']['FaceId']
    return faceId

def detect_faces_from_s3(filename):
    print("Detecting face in " + filename)
    s3_client = boto3.client('s3')
    rekognition_client = boto3.client('rekognition')
    print("Starting detect_faces call")
    response = rekognition_client.detect_faces(Image={'S3Object': {'Bucket': bucketName, 'Name': filename}}, Attributes=['ALL'])
    print("detect_faces response: " + str(response))
    if not response['FaceDetails']:
        print("Deleting " + filename + " from S3")
        s3_client.delete_object(Bucket=bucketName,Key=filename)
        return False
    print("Detected face in " + filename)
    return True

def fetch_image(streamARN, fragmentNumber, serverTimestamp):
    #print(streamARN, fragmentNumber, serverTimestamp)
    kvs_client = boto3.client('kinesisvideo')
    kvs_endpoint = kvs_client.get_data_endpoint(
            APIName="GET_HLS_STREAMING_SESSION_URL",
            StreamARN=streamARN
        )['DataEndpoint']
        
    kvam_client = boto3.client('kinesis-video-archived-media', endpoint_url=kvs_endpoint)
    video_stream_url = kvam_client.get_hls_streaming_session_url(
            StreamARN=streamARN,
            PlaybackMode="LIVE_REPLAY",
            HLSFragmentSelector={
                'FragmentSelectorType': 'SERVER_TIMESTAMP',
                'TimestampRange': {
                    'StartTimestamp': serverTimestamp
                }
            }
        )['HLSStreamingSessionURL']
        
    #print("Capturing video from: " + video_stream_url)
    video_capture_client = cv2.VideoCapture(video_stream_url)
    filename = fragmentNumber + ".jpg"
    temp_filename = "temp_frame.jpg"
    temp_filename_s3 = "temp_frame_s3.jpg"
    s3_client = boto3.client('s3')
    no_faces_detected = False
    success = True
    while(success):
        # Capture frame-by-frame
        success, image_frame = video_capture_client.read()
        
        if image_frame is not None:
            # Display the resulting frame
            video_capture_client.set(1, int(video_capture_client.get(cv2.CAP_PROP_FRAME_COUNT) / 2) - 1)
            #print("CV writing to file - " + temp_filename)
            cv2.imwrite('/tmp/' + temp_filename, image_frame)
            #print("Uploading to S3 bucket: " + bucketName)
            s3_client.upload_file(
                '/tmp/' + temp_filename,
                bucketName,
                temp_filename_s3,
                ExtraArgs={'ACL':'public-read'}
            )
            if detect_faces_from_s3(temp_filename_s3):
                s3_client.upload_file(
                '/tmp/' + temp_filename,
                bucketName,
                filename,
                ExtraArgs={'ACL':'public-read'})
                s3_client.delete_object(Bucket=bucketName,Key=temp_filename_s3)
                print("Uploaded to S3")
            else:
                no_faces_detected = True
            video_capture_client.release()
            break
        else:
            break
    video_capture_client.release()
    cv2.destroyAllWindows()
    if no_faces_detected:
        return None, None
    else:
        # https://knownfacesphotos.s3.amazonaws.com/554880.JPG
        s3_image_link = "https://%s.s3.amazonaws.com/%s" % (bucketName, filename)
        print("S3 Image Link: " + s3_image_link)
        return filename, s3_image_link

def update_visitors_with_image(faceId, image_name):
    data = [{
        "bucket" : "knownfacesphotos",        
        "createdTimestamp" : str(datetime.datetime.now()),
        "objectKey" : image_name
    }]
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table('visitors')
    response = table.update_item(
        Key={
            'faceId': faceId,
        },
        UpdateExpression="SET photos = list_append(photos, :i)",
        ExpressionAttributeValues={
            ':i': data,
        },
        ReturnValues="UPDATED_NEW"
    )
    #print(response)

def lambda_handler(event, context):
    #print(event['Records'])
    for record in event['Records']:
        #Kinesis data is base64 encoded so decode here
        payload=json.loads(base64.b64decode(record["kinesis"]["data"]))
        print("Decoded payload: " + str(payload))
        streamARN = payload["InputInformation"]["KinesisVideo"]["StreamArn"]
        fragmentNumber = payload["InputInformation"]["KinesisVideo"]["FragmentNumber"]
        serverTimestamp = payload["InputInformation"]["KinesisVideo"]["ServerTimestamp"]
        # Parse face ID. If multiple face IDs matched, go with the one having highest similarity
        faceSearchResponse = payload["FaceSearchResponse"]
        matched, faceId = parse_face_search_response(faceSearchResponse)
        if (matched == -1):
            print("No faces detected")
        elif (matched == 1):
            # Retrieve details from database for the face ID
            print("Face ID: " + faceId)
            faceDetails = get_face_details(faceId)
            print("FaceDetails: %s" % faceDetails)
            if faceDetails:
                print("FaceID exists in DynamoDB")
                phoneNumber = parse_phone_number(faceDetails)
                #print(phoneNumber)
                result = check_otp_existence(faceId)
                if not result:
                    image_name, image_link = fetch_image(streamARN, fragmentNumber, serverTimestamp)
                    if image_name and detect_faces_from_s3(image_name):
                        generate_store_send_otp(faceId, phoneNumber)
                        update_visitors_with_image(faceId, image_name)
                        print("Completed fetching image")
                else:
                    print("OTP already sent for this visitor. Not fetching image or updating database")
            else:
                print("FaceID does not exist in DynamoDB")
        elif (matched == 0):
            # Unrecognized face
            print("Unrecognized face")
            image_name, image_link = fetch_image(streamARN, fragmentNumber, serverTimestamp)
            print("Completed fetching image")
            if image_name:# and detect_faces_from_s3(image_name):
                faceId = collection_insert(image_name)
                print("Assigning new faceID: " + faceId)
                # https://ownerportal.s3.amazonaws.com/index.html?fragmentNumber=10a
                msg = "You have a new visitor Sabby,  Please authorize using the following link - http://frontend-owner.s3-website-us-east-1.amazonaws.com?fragmentNumber=" + fragmentNumber
                send_message(ownerPhoneNumber, msg)