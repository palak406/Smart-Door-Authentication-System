import json
import datetime
import boto3
import random

bucket = 'owner-photos'
collection_id = "collection1"

def generate_store_send_otp(faceId, phoneNumber):
    otp = random.randint(100000,999999) #TODO: Randomize OTP
    expiration_time = 300
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table('passcodes')
    response = table.get_item(Key={'faceId': faceId})
    print(response)
    if response.get("Item", None):
        print("OTP Already sent")
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

def parse_face_response(response, image):
    faceId = None
    for face in response['Faces']:
        if image == face['ExternalImageId']:
            faceId = face['FaceId']
            break
    return faceId

def collection_faceId(image):
    client = boto3.client('rekognition')
    nextToken = None
    while(True):
        if nextToken:
            response = client.list_faces(CollectionId=collection_id, NextToken=nextToken)
            faceId = parse_face_response(response, image)
        else:
            response = client.list_faces(CollectionId=collection_id)
            faceId = parse_face_response(response, image)
            break
        if faceId:
            break
        nextToken = response.get('NextToken', None)
    return faceId

def dynamodb_insert(name, phoneNumber, faceId, image):
    client = boto3.resource('dynamodb')
    table = client.Table('visitors')
    data = {
              "faceId": faceId,
              "name": name,
              "phoneNumber": phoneNumber,
              "photos": [
                          {
                            "objectKey": image,
                            "bucket": bucket,
                            "createdTimestamp": str(datetime.datetime.now())
                          }
                         ]
            }
    response = table.put_item(Item=data)


def lambda_handler(event, context):
    # TODO implement
    
    print(event)
    print(dir(event))
    name = event['name']
    phoneNumber = event['number']
    fragmentNumber = event['fragmentNumber']
    print(name, phoneNumber,fragmentNumber)
    image = fragmentNumber+'.jpg'
    faceId = collection_faceId(image)
    if faceId:
        dynamodb_insert(name, phoneNumber, faceId, image)
        generate_store_send_otp(faceId, phoneNumber)
    else:
        print("Failed to retrieve FaceId for image %s"%image)
    
    response = {
            "response_code": 200,
            "headers": {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            "body": "Updated Visitor Information!"
            }
    return response