import json
import boto3
from boto3.dynamodb.conditions import Key, Attr


dynamodb = boto3.resource('dynamodb')
table1 = dynamodb.Table('passcodes')
table2 = dynamodb.Table('visitors')

def validate_otp(otp):
    fe = Attr("OTP").eq(otp)
    record = table1.scan()
    id=0
    res="Access Denied"
    for i in record['Items']:
        if otp == str(i['OTP']):
            id = i['faceId']
            resposne = table1.delete_item(Key={"faceId":id})
            break
    print("FaceId found:%s" %id)
    if id:
        name = get_name(id)
        res = "Access Granted!!! Welcome " + name + "!" 
    return res
    
def get_name(id):
    name = None
    response = table2.get_item(Key={"faceId":id})
    item = response.get('Item',None)
    if item:
        name = item['name']
    return name
    
def lambda_handler(event, context):
    print("event", event)
    print(dir(event))
    otp = event['otp']
    print(otp)
    
    result= validate_otp(otp) 
    
    response = {
            "response_code": 200,
            "headers": {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            "body": " "+result
            }
    return response