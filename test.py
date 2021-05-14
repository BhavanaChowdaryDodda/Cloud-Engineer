import yaml
import time
import boto3
import paramiko
with open(r'assignment.yaml') as file:
    val= yaml.load(file)


for i in val['server']['volumes']:
  if i['mount'] == "/":
    size=i['size_gb']
    device=i['device']

ec2 = boto3.client("ec2", region_name=val['server']['region_name'],aws_access_key_id=val['server']['aws_access_key_id'],aws_secret_access_key=val['server']['aws_secret_access_key'])


reservations = ec2.describe_instances(Filters=[
    {
        "Name": "instance-state-name",
        "Values": ["running"],
    }
]).get("Reservations")


for reservation in reservations:
    for instance in reservation["Instances"]:
        if instance['ImageId'] == val['server']['Image_Id']:
            instance_id = instance["InstanceId"]
            ec2.terminate_instances(InstanceIds=[instance_id])
            
response = ec2.describe_key_pairs()
flag=0

for i in response['KeyPairs']:
 if i['KeyName'] == val['server']['key_pair'] :
  flag=1
  print("Using the key pair : "+val['server']['key_pair'])
  

response = ec2.run_instances(
    
    InstanceType=val['server']['instance_type'],
    ImageId=val['server']['Image_Id'],
    KeyName=val['server']['key_pair'],
    MaxCount=val['server']['max_count'],
    MinCount=val['server']['min_count'],
    BlockDeviceMappings=[
        {
            'DeviceName': device,
            'Ebs': {
                'VolumeSize': size,
            },
        },
    ]
)

for i in response['Instances']:
  if i['ImageId'] == val['server']['Image_Id']:
   print(i['InstanceId'])
   Instid=i['InstanceId']
   
response = ec2.describe_security_groups()


ports=[]
for i in response['SecurityGroups']:
   for j in i['IpPermissions']:
       try:
          ports.append(j['FromPort'])
       except Exception:
          continue
          
if 22 not in ports:
 data = ec2.authorize_security_group_ingress(
        GroupId=response['Instances'][0]['SecurityGroups'][0]['GroupId'],
        IpPermissions=[
            {'IpProtocol': 'tcp',
             'FromPort': 22,
             'ToPort': 22,
             'IpRanges': [{'CidrIp': '0.0.0.0/0'}]}
        ])


for i in val['server']['volumes']:
  if i['mount'] == "/data":
    size=i['size_gb']
    device=i['device']
    mount=i['mount']

ebs_vol = ec2.create_volume(
    Size=size,
    AvailabilityZone=val['server']['availability_zone']
)

volume_id = ebs_vol['VolumeId']

# check that the EBS volume has been created successfully
if ebs_vol['ResponseMetadata']['HTTPStatusCode'] == 200:
    print "Successfully created Volume! " + volume_id

time.sleep(30)

attach_resp = ec2.attach_volume(
    VolumeId=volume_id,
    InstanceId=Instid,
    Device=device
)


reservations = ec2.describe_instances(Filters=[
    {
        "Name": "instance-state-name",
        "Values": ["running"],
    }
]).get("Reservations")


for reservation in reservations:
    for instance in reservation["Instances"]:
        if instance['ImageId'] == val['server']['Image_Id']:
            public_address=instance['PublicIpAddress']
            

time.sleep(30)



key = paramiko.RSAKey.from_private_key_file(val['server']['path_pem'])
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())


client.connect(hostname=public_address, username="ec2-user", pkey=key)


cmd="sudo mkfs -t xfs "+device+"; sudo mkdir "+mount+";sudo mount "+device+"  "+mount
stdin, stdout, stderr = client.exec_command(cmd)

for i in val['server']['users']:
 user_name=i['login']
 public_key=i['ssh_key']
 cmd="sudo adduser "+user_name+";sudo su -  "+user_name+" bash -c \" mkdir .ssh;chmod 700 .ssh;touch .ssh/authorized_keys;chmod 600 .ssh/authorized_keys;echo \'"+public_key+"\' >> .ssh/authorized_keys\""
 stdin, stdout, stderr = client.exec_command(cmd)
client.close()

