
import boto3
import json
from datetime import datetime, timedelta

def get_reservation_utilization():
    ce_client = boto3.client('ce')
    today = datetime.now()
    six_months_ago = today - timedelta(days=180)
    
    response = ce_client.get_reservation_utilization(
        TimePeriod={
            'Start': six_months_ago.strftime('%Y-%m-%d'),
            'End': today.strftime('%Y-%m-%d')
        },
        Granularity='MONTHLY'
    )
    
    return response['UtilizationsByTime']

def get_cost_and_usage():
    ce_client = boto3.client('ce')
    today = datetime.now()
    six_months_ago = today - timedelta(days=180)
    
    response = ce_client.get_cost_and_usage(
        TimePeriod={
            'Start': six_months_ago.strftime('%Y-%m-%d'),
            'End': today.strftime('%Y-%m-%d')
        },
        Granularity='MONTHLY',
        Metrics=['UnblendedCost'],
        GroupBy=[
            {
                'Type': 'DIMENSION',
                'Key': 'SERVICE'
            }
        ]
    )
    
    results = response['ResultsByTime']
    
    services_data = {}
    
    for result in results:
        month_start_date = datetime.strptime(result['TimePeriod']['Start'], '%Y-%m-%d')
        month = month_start_date.strftime('%Y/%m')
        for group in result['Groups']:
            service_name = group['Keys'][0]
            cost = float(group['Metrics']['UnblendedCost']['Amount'])
            
            if cost > 10: # Apply the $10 filter here
                if service_name not in services_data:
                    services_data[service_name] = {
                        'monthly_expenses': {},
                        'total_cost': 0,
                        'average_cost': 0
                    }
                
                services_data[service_name]['monthly_expenses'][month] = cost
            
    for service_name, data in services_data.items():
        total_cost = sum(data['monthly_expenses'].values())
        average_cost = total_cost / len(data['monthly_expenses']) if data['monthly_expenses'] else 0
        services_data[service_name]['total_cost'] = total_cost
        services_data[service_name]['average_cost'] = average_cost
        
    return services_data

def get_running_ec2_instances():
    ec2_client = boto3.client('ec2')
    optimizer_client = boto3.client('compute-optimizer')
    sts_client = boto3.client('sts')
    
    # Get account ID and region
    account_id = sts_client.get_caller_identity()['Account']
    region = ec2_client.meta.region_name

    response = ec2_client.describe_instances(
        Filters=[
            {
                'Name': 'instance-state-name',
                'Values': ['running']
            }
        ]
    )
    
    instances = []
    instance_arns = []
    for reservation in response['Reservations']:
        for instance in reservation['Instances']:
            instance_id = instance['InstanceId']
            instance_arn = f"arn:aws:ec2:{region}:{account_id}:instance/{instance_id}"
            instance_arns.append(instance_arn)
            
            description = ''
            if 'Tags' in instance:
                for tag in instance['Tags']:
                    if tag['Key'] == 'Name':
                        description = tag['Value']
                        break
            instances.append({
                'InstanceId': instance_id,
                'Description': description,
                'InstanceType': instance['InstanceType'],
                'Recommendations': []
            })

    if instance_arns:
        recommendations_response = optimizer_client.get_ec2_instance_recommendations(
            instanceArns=instance_arns
        )
        
        for rec in recommendations_response.get('instanceRecommendations', []):
            for inst in instances:
                if inst['InstanceId'] == rec['instanceArn'].split('/')[-1]:
                    inst['Recommendations'].append({
                        'Finding': rec.get('finding'),
                        'RecommendationOptions': rec.get('recommendationOptions', [])
                    })
                    break
            
    return instances

def get_cpu_utilization(instance_id):
    cw_client = boto3.client('cloudwatch')
    today = datetime.now()
    seven_days_ago = today - timedelta(days=7)
    
    response = cw_client.get_metric_data(
        MetricDataQueries=[
            {
                'Id': 'cpu_utilization',
                'MetricStat': {
                    'Metric': {
                        'Namespace': 'AWS/EC2',
                        'MetricName': 'CPUUtilization',
                        'Dimensions': [
                            {
                                'Name': 'InstanceId',
                                'Value': instance_id
                            }
                        ]
                    },
                    'Period': 604800, # 7 days
                    'Stat': 'Average'
                },
                'ReturnData': True
            }
        ],
        StartTime=seven_days_ago,
        EndTime=today
    )
    
    if response['MetricDataResults'][0]['Values']:
        return sum(response['MetricDataResults'][0]['Values']) / len(response['MetricDataResults'][0]['Values'])
    return 0

def get_ebs_volumes():
    ec2_client = boto3.client('ec2')
    response = ec2_client.describe_volumes()
    
    volumes = []
    for volume in response['Volumes']:
        in_use = False
        if volume['Attachments']:
            in_use = True
            
        volumes.append({
            'VolumeId': volume['VolumeId'],
            'VolumeType': volume['VolumeType'],
            'Size': volume['Size'],
            'InUse': in_use,
            'Iops': volume.get('Iops', 'N/A'),
            'Throughput': volume.get('Throughput', 'N/A'),
            'CreateTime': volume['CreateTime'].isoformat()
        })
        
    return volumes

def get_ebs_snapshots():
    ec2_client = boto3.client('ec2')
    dlm_client = boto3.client('dlm')

    # Get all lifecycle policies
    lifecycle_policies = dlm_client.get_lifecycle_policies()['Policies']

    response = ec2_client.describe_snapshots(OwnerIds=['self'])
    
    snapshots = []
    for snapshot in response['Snapshots']:
        volume_id = snapshot.get('VolumeId', 'N/A')
        volume_size = 'N/A'
        if volume_id != 'N/A':
            try:
                volume_response = ec2_client.describe_volumes(VolumeIds=[volume_id])
                if volume_response['Volumes']:
                    volume_size = volume_response['Volumes'][0]['Size']
            except ec2_client.exceptions.ClientError as e:
                if e.response['Error']['Code'] == 'InvalidVolume.NotFound':
                    volume_size = 'N/A (Volume not found)'
                else:
                    raise

        # Check for lifecycle policies
        lifecycle_policy = 'N/A'
        for policy in lifecycle_policies:
            if policy['State'] == 'ENABLED':
                for target_tag in policy['PolicyDetails']['TargetTags']:
                    for snapshot_tag in snapshot.get('Tags', []):
                        if target_tag['Key'] == snapshot_tag['Key'] and target_tag['Value'] == snapshot_tag['Value']:
                            lifecycle_policy = policy['PolicyId']
                            break
                    if lifecycle_policy != 'N/A':
                        break

        snapshots.append({
            'SnapshotId': snapshot['SnapshotId'],
            'VolumeId': volume_id,
            'SnapshotSize': snapshot['VolumeSize'],
            'VolumeSize': volume_size,
            'StartTime': snapshot['StartTime'].isoformat(),
            'LifecyclePolicy': lifecycle_policy
        })
        
    return snapshots

def get_s3_data():
    s3_client = boto3.client('s3')
    cw_client = boto3.client('cloudwatch')
    
    buckets_data = []
    
    response = s3_client.list_buckets()
    
    for bucket in response['Buckets']:
        bucket_name = bucket['Name']
        
        # Get bucket size
        try:
            bucket_size_bytes = 0
            paginator = cw_client.get_paginator('list_metrics')
            for page in paginator.paginate(Namespace='AWS/S3', MetricName='BucketSizeBytes', Dimensions=[{'Name':'BucketName', 'Value':bucket_name},{'Name':'StorageType', 'Value':'StandardStorage'}]):
                if page['Metrics']:
                    response = cw_client.get_metric_statistics(
                        Namespace='AWS/S3',
                        MetricName='BucketSizeBytes',
                        Dimensions=page['Metrics'][0]['Dimensions'],
                        StartTime=datetime.now() - timedelta(days=2),
                        EndTime=datetime.now(),
                        Period=86400,
                        Statistics=['Average']
                    )
                    if response['Datapoints']:
                        bucket_size_bytes = response['Datapoints'][0]['Average']
                        break
            bucket_size_mb = round(bucket_size_bytes / (1024 * 1024), 2) if bucket_size_bytes != 'N/A' else 'N/A'
        except Exception as e:
            print(f"Could not get size for bucket {bucket_name}: {e}")
            bucket_size_mb = 'N/A'

        # Get lifecycle policy
        lifecycle_policy_description = []
        tiering = 'N/A'
        try:
            lifecycle_response = s3_client.get_bucket_lifecycle_configuration(Bucket=bucket_name)
            if 'Rules' in lifecycle_response:
                rules = lifecycle_response['Rules']
                policy_details = []
                for rule in rules:
                    rule_description = f"Rule ID: {rule['ID']}, Status: {rule['Status']}"
                    if 'Expiration' in rule:
                        if 'Days' in rule['Expiration']:
                            rule_description += f", Expires after {rule['Expiration']['Days']} days"
                        elif 'Date' in rule['Expiration']:
                            rule_description += f", Expires on {rule['Expiration']['Date'].isoformat()}"
                    if 'Transitions' in rule:
                        for transition in rule['Transitions']:
                            rule_description += f", Transitions to {transition['StorageClass']} after {transition['Days']} days"
                            tiering = transition['StorageClass'] # Assuming first transition defines tiering
                    if 'NoncurrentVersionExpiration' in rule:
                        rule_description += f", Noncurrent versions expire after {rule['NoncurrentVersionExpiration']['NoncurrentDays']} days"
                    if 'AbortIncompleteMultipartUpload' in rule:
                        rule_description += f", Aborts incomplete multipart uploads after {rule['AbortIncompleteMultipartUpload']['DaysAfterInitiation']} days"
                    policy_details.append(rule_description)
                lifecycle_policy_description = policy_details
        except s3_client.exceptions.ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchLifecycleConfiguration':
                lifecycle_policy_description = []
            else:
                print(f"Could not get lifecycle policy for bucket {bucket_name}: {e}")
                lifecycle_policy_description = 'Error retrieving policy.'

        buckets_data.append({
            'BucketName': bucket_name,
            'StorageUsageMB': bucket_size_mb,
            'LifecyclePolicy': lifecycle_policy_description,
            'Tiering': tiering
        })
        
    return buckets_data

def get_network_topology():
    ec2_client = boto3.client('ec2')
    cw_client = boto3.client('cloudwatch')

    vpcs = ec2_client.describe_vpcs()['Vpcs']
    subnets = ec2_client.describe_subnets()['Subnets']
    internet_gateways = ec2_client.describe_internet_gateways()['InternetGateways']
    nat_gateways = ec2_client.describe_nat_gateways()['NatGateways']
    transit_gateways = ec2_client.describe_transit_gateways()['TransitGateways']
    route_tables = ec2_client.describe_route_tables()['RouteTables']

    vpc_data = []
    lost_nat_gateways = []

    today = datetime.now()
    seven_days_ago = today - timedelta(days=7)

    for nat_gateway in nat_gateways:
        nat_gateway_id = nat_gateway['NatGatewayId']
        
        # Get BytesOutAndIn metric for the last 7 days
        response = cw_client.get_metric_statistics(
            Namespace='AWS/NATGateway',
            MetricName='BytesOutAndIn',
            Dimensions=[
                {
                    'Name': 'NatGatewayId',
                    'Value': nat_gateway_id
                }
            ],
            StartTime=seven_days_ago,
            EndTime=today,
            Period=604800, # 7 days
            Statistics=['Sum']
        )
        
        total_bytes = 0
        if response['Datapoints']:
            total_bytes = response['Datapoints'][0]['Sum']
        
        # Consider NAT Gateway lost if total bytes is very low (e.g., < 1KB)
        if total_bytes < 1024: # 1KB threshold
            lost_nat_gateways.append({
                'NatGatewayId': nat_gateway_id,
                'State': nat_gateway['State'],
                'VpcId': nat_gateway['VpcId'],
                'TotalBytesOutAndInLast7Days': f"{total_bytes:.2f} bytes"
            })

    for vpc in vpcs:
        vpc_id = vpc['VpcId']
        vpc_subnets = []

        for subnet in subnets:
            if subnet['VpcId'] == vpc_id:
                subnet_id = subnet['SubnetId']
                is_public = False

                # Check if subnet is public
                for route_table in route_tables:
                    for association in route_table['Associations']:
                        if association.get('SubnetId') == subnet_id:
                            for route in route_table['Routes']:
                                if route.get('GatewayId') and route.get('GatewayId').startswith('igw-'):
                                    is_public = True
                                    break
                            break
                    if is_public:
                        break

                nat_gateway_id_in_subnet = 'N/A'
                for nat_gateway in nat_gateways:
                    if nat_gateway['SubnetId'] == subnet_id:
                        nat_gateway_id_in_subnet = nat_gateway['NatGatewayId']
                        break

                vpc_subnets.append({
                    'SubnetId': subnet_id,
                    'AvailabilityZone': subnet['AvailabilityZone'],
                    'IsPublic': is_public,
                    'NatGatewayId': nat_gateway_id_in_subnet
                })

        internet_gateway_id = 'N/A'
        for igw in internet_gateways:
            for attachment in igw['Attachments']:
                if attachment['VpcId'] == vpc_id:
                    internet_gateway_id = igw['InternetGatewayId']
                    break
            if internet_gateway_id != 'N/A':
                break

        transit_gateway_attachments = []
        for tgw in transit_gateways:
            for attachment in tgw.get('Attachments', []):
                if attachment['VpcId'] == vpc_id:
                    transit_gateway_attachments.append(attachment['TransitGatewayAttachmentId'])

        vpc_data.append({
            'VpcId': vpc_id,
            'InternetGatewayId': internet_gateway_id,
            'TransitGatewayAttachments': transit_gateway_attachments,
            'Subnets': vpc_subnets
        })

    return {
        'VpcData': vpc_data,
        'LostNatGateways': lost_nat_gateways
    }

def get_eks_data():
    eks_client = boto3.client('eks')
    ec2_client = boto3.client('ec2')
    cw_client = boto3.client('cloudwatch')

    clusters_data = []

    cluster_names = eks_client.list_clusters()['clusters']

    for cluster_name in cluster_names:
        cluster_info = eks_client.describe_cluster(name=cluster_name)['cluster']
        
        nodes = []
        uses_karpenter = False
        try:
            instances_response = ec2_client.describe_instances(
                Filters=[
                    {
                        'Name': 'tag-key',
                        'Values': ['*cluster-name']
                    },
                    {
                        'Name': 'tag-value',
                        'Values': [cluster_name]
                    }
                ]
            )
            for reservation in instances_response['Reservations']:
                for instance in reservation['Instances']:
                    is_karpenter_node = False
                    for tag in instance.get('Tags', []):
                        if "karpenter" in tag['Key'].lower():
                            is_karpenter_node = True
                            uses_karpenter = True
                            break

            for reservation in instances_response['Reservations']:
                for instance in reservation['Instances']:
                    is_karpenter_node = False
                    for tag in instance.get('Tags', []):
                        if "karpenter" in tag['Key'].lower():
                            is_karpenter_node = True
                            uses_karpenter = True
                            break
                    
                    # Get memory utilization
                    today = datetime.now()
                    start_time = today - timedelta(minutes=5)
                    
                    memory_utilization_response = cw_client.get_metric_statistics(
                        Namespace='CWAgent',
                        MetricName='MemoryUtilization',
                        Dimensions=[
                            {
                                'Name': 'InstanceId',
                                'Value': instance['InstanceId']
                            }
                        ],
                        StartTime=start_time,
                        EndTime=today,
                        Period=300,
                        Statistics=['Average']
                    )
                    
                    avg_memory_utilization = 0
                    if memory_utilization_response['Datapoints']:
                        avg_memory_utilization = memory_utilization_response['Datapoints'][0]['Average']

                    nodes.append({
                        'InstanceId': instance['InstanceId'],
                        'InstanceType': instance['InstanceType'],
                        'IsKarpenterNode': is_karpenter_node,
                        'AverageMemoryUtilization': f"{avg_memory_utilization:.2f}%"
                    })
        except Exception as e:
            print(f"Could not get nodes for cluster {cluster_name}: {e}")


        clusters_data.append({
            'ClusterName': cluster_name,
            'Version': cluster_info['version'],
            'Platform': cluster_info['platformVersion'],
            'Nodes': nodes,
            'UsesKarpenter': uses_karpenter
        })

    return clusters_data

def get_rds_data():
    rds_client = boto3.client('rds')
    cw_client = boto3.client('cloudwatch')
    
    db_instances_data = []
    
    paginator = rds_client.get_paginator('describe_db_instances')
    for page in paginator.paginate():
        for db_instance in page['DBInstances']:
            db_instance_id = db_instance['DBInstanceIdentifier']
            
            # Get CPU Utilization
            today = datetime.now()
            seven_days_ago = today - timedelta(days=7)
            
            response = cw_client.get_metric_data(
                MetricDataQueries=[
                    {
                        'Id': 'cpu_utilization',
                        'MetricStat': {
                            'Metric': {
                                'Namespace': 'AWS/RDS',
                                'MetricName': 'CPUUtilization',
                                'Dimensions': [
                                    {
                                        'Name': 'DBInstanceIdentifier',
                                        'Value': db_instance_id
                                    }
                                ]
                            },
                            'Period': 604800, # 7 days
                            'Stat': 'Average'
                        },
                        'ReturnData': True
                    }
                ],
                StartTime=seven_days_ago,
                EndTime=today
            )
            
            avg_cpu = 0
            if response['MetricDataResults'][0]['Values']:
                avg_cpu = sum(response['MetricDataResults'][0]['Values']) / len(response['MetricDataResults'][0]['Values'])

            # Get Snapshots
            snapshots_response = rds_client.describe_db_snapshots(DBInstanceIdentifier=db_instance_id)
            snapshots = [{
                'SnapshotId': s['DBSnapshotIdentifier'],
                'SnapshotCreateTime': s['SnapshotCreateTime'].isoformat(),
                'Encrypted': s['Encrypted']
            } for s in snapshots_response['DBSnapshots']]

            db_instances_data.append({
                'DBInstanceIdentifier': db_instance_id,
                'DBInstanceClass': db_instance['DBInstanceClass'],
                'Engine': db_instance['Engine'],
                'DBInstanceStatus': db_instance['DBInstanceStatus'],
                'MultiAZ': db_instance['MultiAZ'],
                'BackupRetentionPeriod': db_instance['BackupRetentionPeriod'],
                'AverageCPUUtilization': f"{avg_cpu:.2f}%",
                'Snapshots': snapshots
            })
            
    return db_instances_data

def get_dynamodb_data():
    dynamodb_client = boto3.client('dynamodb')
    cw_client = boto3.client('cloudwatch')
    
    tables_data = []
    
    paginator = dynamodb_client.get_paginator('list_tables')
    for page in paginator.paginate():
        for table_name in page['TableNames']:
            table_info = dynamodb_client.describe_table(TableName=table_name)['Table']
            
            # Get Consumed Capacity
            today = datetime.now()
            seven_days_ago = today - timedelta(days=7)
            
            read_capacity_response = cw_client.get_metric_statistics(
                Namespace='AWS/DynamoDB',
                MetricName='ConsumedReadCapacityUnits',
                Dimensions=[{'Name': 'TableName', 'Value': table_name}],
                StartTime=seven_days_ago,
                EndTime=today,
                Period=604800,
                Statistics=['Average']
            )
            
            write_capacity_response = cw_client.get_metric_statistics(
                Namespace='AWS/DynamoDB',
                MetricName='ConsumedWriteCapacityUnits',
                Dimensions=[{'Name': 'TableName', 'Value': table_name}],
                StartTime=seven_days_ago,
                EndTime=today,
                Period=604800,
                Statistics=['Average']
            )

            avg_read_capacity = 0
            if read_capacity_response['Datapoints']:
                avg_read_capacity = read_capacity_response['Datapoints'][0]['Average']

            avg_write_capacity = 0
            if write_capacity_response['Datapoints']:
                avg_write_capacity = write_capacity_response['Datapoints'][0]['Average']

            # Continuous Backups / PITR
            continuous_backups_info = dynamodb_client.describe_continuous_backups(TableName=table_name)
            pitr_status = continuous_backups_info['ContinuousBackupsDescription']['PointInTimeRecoveryDescription']['PointInTimeRecoveryStatus']

            # On-demand backups
            backups_response = dynamodb_client.list_backups(TableName=table_name)
            backups = [{
                'BackupArn': b['BackupArn'],
                'BackupCreationDateTime': b['BackupCreationDateTime'].isoformat(),
                'BackupStatus': b['BackupStatus']
            } for b in backups_response['BackupSummaries']]

            provisioned_throughput = table_info.get('ProvisionedThroughput')
            if provisioned_throughput and 'LastIncreaseDateTime' in provisioned_throughput:
                provisioned_throughput['LastIncreaseDateTime'] = provisioned_throughput['LastIncreaseDateTime'].isoformat()
            if provisioned_throughput and 'LastDecreaseDateTime' in provisioned_throughput:
                provisioned_throughput['LastDecreaseDateTime'] = provisioned_throughput['LastDecreaseDateTime'].isoformat()

            tables_data.append({
                'TableName': table_name,
                'TableSizeBytes': table_info['TableSizeBytes'],
                'ItemCount': table_info['ItemCount'],
                'ProvisionedThroughput': provisioned_throughput or 'On-demand',
                'AverageConsumedReadCapacity': avg_read_capacity,
                'AverageConsumedWriteCapacity': avg_write_capacity,
                'PointInTimeRecoveryStatus': pitr_status,
                'Backups': backups
            })
            
    return tables_data

def get_elasticache_data():
    elasticache_client = boto3.client('elasticache')
    cw_client = boto3.client('cloudwatch')
    
    clusters_data = []
    
    paginator = elasticache_client.get_paginator('describe_cache_clusters')
    for page in paginator.paginate(ShowCacheNodeInfo=True):
        for cluster in page['CacheClusters']:
            cluster_id = cluster['CacheClusterId']
            
            # Get CPU and Memory Utilization
            today = datetime.now()
            seven_days_ago = today - timedelta(days=7)
            
            cpu_response = cw_client.get_metric_statistics(
                Namespace='AWS/ElastiCache',
                MetricName='CPUUtilization',
                Dimensions=[{'Name': 'CacheClusterId', 'Value': cluster_id}],
                StartTime=seven_days_ago,
                EndTime=today,
                Period=604800,
                Statistics=['Average']
            )
            
            memory_response = cw_client.get_metric_statistics(
                Namespace='AWS/ElastiCache',
                MetricName='FreeableMemory',
                Dimensions=[{'Name': 'CacheClusterId', 'Value': cluster_id}],
                StartTime=seven_days_ago,
                EndTime=today,
                Period=604800,
                Statistics=['Average']
            )

            avg_cpu = 0
            if cpu_response['Datapoints']:
                avg_cpu = cpu_response['Datapoints'][0]['Average']

            avg_freeable_memory = 0
            if memory_response['Datapoints']:
                avg_freeable_memory = memory_response['Datapoints'][0]['Average']

            # Get Snapshots
            snapshots_response = elasticache_client.describe_snapshots(CacheClusterId=cluster_id)
            snapshots = [{
                **s,
                'CacheClusterCreateTime': s['CacheClusterCreateTime'].isoformat(),
                'NodeSnapshots': [{
                    **ns,
                    'CacheNodeCreateTime': ns['CacheNodeCreateTime'].isoformat(),
                    'SnapshotCreateTime': ns['SnapshotCreateTime'].isoformat()
                } for ns in s.get('NodeSnapshots', [])]
            } for s in snapshots_response['Snapshots']]

            clusters_data.append({
                'CacheClusterId': cluster_id,
                'CacheNodeType': cluster['CacheNodeType'],
                'Engine': cluster['Engine'],
                'EngineVersion': cluster['EngineVersion'],
                'NumCacheNodes': cluster['NumCacheNodes'],
                'SnapshotRetentionLimit': cluster['SnapshotRetentionLimit'],
                'AverageCPUUtilization': f"{avg_cpu:.2f}%",
                'AverageFreeableMemory': f"{avg_freeable_memory / (1024*1024):.2f} MB",
                'Snapshots': snapshots
            })
            
    return clusters_data

def get_efs_data():
    efs_client = boto3.client('efs')
    
    efs_data = []
    
    file_systems = efs_client.describe_file_systems()['FileSystems']
    
    for fs in file_systems:
        fs_id = fs['FileSystemId']
        
        mount_targets = efs_client.describe_mount_targets(FileSystemId=fs_id)['MountTargets']
        
        backup_policy = efs_client.describe_backup_policy(FileSystemId=fs_id).get('BackupPolicy', {})
        
        lifecycle_policies = fs.get('LifecyclePolicies', [])
        for policy in lifecycle_policies:
            if 'TransitionToIA' in policy:
                policy['TransitionToIA'] = str(policy['TransitionToIA'])
            if 'TransitionToPrimaryStorageClass' in policy:
                policy['TransitionToPrimaryStorageClass'] = str(policy['TransitionToPrimaryStorageClass'])

        efs_data.append({
            'FileSystemId': fs_id,
            'Name': fs.get('Name', 'N/A'),
            'SizeInBytes': fs['SizeInBytes']['Value'],
            'ThroughputMode': fs['ThroughputMode'],
            'ProvisionedThroughputInMibps': fs.get('ProvisionedThroughputInMibps'),
            'LifecyclePolicies': lifecycle_policies,
            'IsUsed': len(mount_targets) > 0,
            'BackupPolicy': backup_policy.get('Status', 'DISABLED'),
        })
        
    return efs_data

def get_load_balancers_data():
    elbv2_client = boto3.client('elbv2')
    
    load_balancers_data = []
    
    load_balancers = elbv2_client.describe_load_balancers()['LoadBalancers']
    
    for lb in load_balancers:
        lb_arn = lb['LoadBalancerArn']
        
        target_groups = elbv2_client.describe_target_groups(LoadBalancerArn=lb_arn)['TargetGroups']
        
        targets_data = []
        for tg in target_groups:
            tg_arn = tg['TargetGroupArn']
            target_health = elbv2_client.describe_target_health(TargetGroupArn=tg_arn)['TargetHealthDescriptions']
            targets_data.append({
                'TargetGroupArn': tg_arn,
                'TargetGroupName': tg['TargetGroupName'],
                'Targets': target_health
            })
            
        load_balancers_data.append({
            'LoadBalancerArn': lb_arn,
            'LoadBalancerName': lb['LoadBalancerName'],
            'Type': lb['Type'],
            'Scheme': lb['Scheme'],
            'InUse': len(target_groups) > 0,
            'TargetGroups': targets_data
        })
        
    return load_balancers_data

def get_cloudwatch_logs_data():
    logs_client = boto3.client('logs')
    
    log_groups_data = []
    
    paginator = logs_client.get_paginator('describe_log_groups')
    for page in paginator.paginate():
        for log_group in page['logGroups']:
            log_groups_data.append({
                'LogGroupName': log_group['logGroupName'],
                'StoredBytes': log_group['storedBytes'],
                'RetentionInDays': log_group.get('retentionInDays', 'Never Expires')
            })
            
    return log_groups_data

def get_lambda_functions_data():
    lambda_client = boto3.client('lambda')
    logs_client = boto3.client('logs')
    
    functions_data = []
    
    paginator = lambda_client.get_paginator('list_functions')
    for page in paginator.paginate():
        for function in page['Functions']:
            function_name = function['FunctionName']
            log_group_name = f"/aws/lambda/{function_name}"
            
            avg_memory_usage = 0
            try:
                # Get log streams, sorted by last event time
                log_streams = logs_client.describe_log_streams(
                    logGroupName=log_group_name,
                    orderBy='LastEventTime',
                    descending=True
                )

                if log_streams['logStreams']:
                    memory_values = []
                    # Paginate through log events to find the last 20 report logs
                    paginator = logs_client.get_paginator('filter_log_events')
                    for stream in log_streams['logStreams']:
                        if len(memory_values) >= 20:
                            break
                        
                        page_iterator = paginator.paginate(
                            logGroupName=log_group_name,
                            logStreamNames=[stream['logStreamName']],
                            filterPattern='REPORT RequestId'
                        )
                        
                        for page in page_iterator:
                            for event in page['events']:
                                if 'REPORT RequestId' in event['message']:
                                    parts = event['message'].split('\t')
                                    for part in parts:
                                        if part.strip().startswith('Max Memory Used:'):
                                            memory_used_str = part.strip().split(':')[1].strip().replace('MB', '').strip()
                                            memory_values.append(int(memory_used_str))
                                            if len(memory_values) >= 20:
                                                break
                            if len(memory_values) >= 20:
                                break
                
                    if memory_values:
                        avg_memory_usage = sum(memory_values) / len(memory_values)

            except logs_client.exceptions.ResourceNotFoundException:
                # Log group might not exist yet if the function has never run
                avg_memory_usage = 0
            except Exception as e:
                print(f"Could not calculate average memory for {function_name}: {e}")
                avg_memory_usage = 0

            functions_data.append({
                'FunctionName': function_name,
                'Runtime': function['Runtime'],
                'MemoryAllocated': function['MemorySize'],
                'AverageMemoryUsage': f"{avg_memory_usage:.2f} MB"
            })
            
    return functions_data

def get_elasticsearch_data():
    es_client = boto3.client('opensearch')
    
    domains_data = []
    
    response = es_client.list_domain_names()
    
    for domain in response['DomainNames']:
        domain_name = domain['DomainName']
        domain_info = es_client.describe_domain(DomainName=domain_name)['DomainStatus']
        
        instance_type = 'N/A'
        instance_count = 0
        storage_size_gb = 'N/A'

        if 'ElasticsearchClusterConfig' in domain_info:
            cluster_config = domain_info['ElasticsearchClusterConfig']
            instance_type = cluster_config.get('InstanceType', 'N/A')
            instance_count = cluster_config.get('InstanceCount', 0)
        
        if 'EBSOptions' in domain_info and domain_info['EBSOptions']['EBSEnabled']:
            storage_size_gb = domain_info['EBSOptions'].get('VolumeSize', 'N/A')

        domains_data.append({
            'DomainName': domain_name,
            'EngineVersion': domain_info.get('ElasticsearchVersion', domain_info.get('EngineVersion', 'N/A')),
            'InstanceType': instance_type,
            'InstanceCount': instance_count,
            'StorageSizeGB': storage_size_gb,
            'Processing': domain_info.get('Processing', False)
        })
        
    return domains_data

def get_kinesis_data():
    kinesis_client = boto3.client('kinesis')
    
    streams_data = []
    
    paginator = kinesis_client.get_paginator('list_streams')
    for page in paginator.paginate():
        for stream_name in page['StreamNames']:
            stream_info = kinesis_client.describe_stream(StreamName=stream_name)['StreamDescription']
            streams_data.append({
                'StreamName': stream_name,
                'StreamStatus': stream_info['StreamStatus'],
                'ShardCount': len(stream_info['Shards'])
            })
            
    return streams_data

def get_sqs_data():
    sqs_client = boto3.client('sqs')
    
    queues_data = []
    
    response = sqs_client.list_queues()
    
    if 'QueueUrls' in response:
        for queue_url in response['QueueUrls']:
            attributes = sqs_client.get_queue_attributes(
                QueueUrl=queue_url,
                AttributeNames=['ApproximateNumberOfMessages', 'VisibilityTimeout']
            )['Attributes']
            queues_data.append({
                'QueueUrl': queue_url,
                'ApproximateNumberOfMessages': attributes.get('ApproximateNumberOfMessages', 'N/A'),
                'VisibilityTimeout': attributes.get('VisibilityTimeout', 'N/A')
            })
            
    return queues_data

def get_sns_data():
    sns_client = boto3.client('sns')
    
    topics_data = []
    
    paginator = sns_client.get_paginator('list_topics')
    for page in paginator.paginate():
        for topic in page['Topics']:
            topic_arn = topic['TopicArn']
            attributes = sns_client.get_topic_attributes(TopicArn=topic_arn)['Attributes']
            topics_data.append({
                'TopicArn': topic_arn,
                'DisplayName': attributes.get('DisplayName', 'N/A')
            })
            
    return topics_data

def get_unused_eips_data():
    ec2_client = boto3.client('ec2')
    
    unused_eips = []
    
    response = ec2_client.describe_addresses()
    
    for eip in response['Addresses']:
        if 'AssociationId' not in eip:
            unused_eips.append({
                'PublicIp': eip.get('PublicIp', 'N/A'),
                'AllocationId': eip.get('AllocationId', 'N/A')
            })
            
    return unused_eips

def get_data_transfer_costs():
    ce_client = boto3.client('ce')
    today = datetime.now()
    one_month_ago = today - timedelta(days=30)
    
    data_transfer_costs = {}
    
    # Define usage types related to data transfer
    data_transfer_usage_types = [
        "DataTransfer-Out-Bytes",
        "DataTransfer-Regional-Bytes",
        "DataTransfer-Out-Bytes (Region to Region)",
        "DataTransfer-In-Bytes"
    ]

    for usage_type in data_transfer_usage_types:
        try:
            response = ce_client.get_cost_and_usage(
                TimePeriod={
                    'Start': one_month_ago.strftime('%Y-%m-%d'),
                    'End': today.strftime('%Y-%m-%d')
                },
                Granularity='MONTHLY',
                Metrics=['UnblendedCost', 'UsageQuantity'],
                Filter={
                    'Dimensions': {
                        'Key': 'USAGE_TYPE',
                        'Values': [usage_type]
                    }
                },
                GroupBy=[
                    {
                        'Type': 'DIMENSION',
                        'Key': 'REGION'
                    }
                ]
            )
            
            total_cost = 0
            total_usage_quantity_gb = 0
            
            for result_by_time in response['ResultsByTime']:
                for group in result_by_time['Groups']:
                    total_cost += float(group['Metrics']['UnblendedCost']['Amount'])
                    usage_quantity_bytes = float(group['Metrics']['UsageQuantity']['Amount'])
                    total_usage_quantity_gb += usage_quantity_bytes / (1024**3)
            
            if total_cost > 0 or total_usage_quantity_gb > 0:
                data_transfer_costs[usage_type] = {
                    'Cost': f"{total_cost:.2f}",
                    'UsageQuantityGB': f"{total_usage_quantity_gb:.2f}"
                }
        except Exception as e:
            print(f"Could not get data transfer costs for usage type {usage_type}: {e}")
            
    # Convert the dictionary to the desired list format
    formatted_data_transfer_costs = [
        {'UsageType': key, **value} for key, value in data_transfer_costs.items()
    ]
            
    return formatted_data_transfer_costs

def get_cloudfront_data():
    cf_client = boto3.client('cloudfront')
    cw_client = boto3.client('cloudwatch')
    
    distributions_data = []
    
    today = datetime.now()
    seven_days_ago = today - timedelta(days=7)

    response = cf_client.list_distributions()
    
    if 'Items' in response['DistributionList']:
        for dist_summary in response['DistributionList']['Items']:
            dist_id = dist_summary['Id']
            
            # Get detailed distribution config
            dist_config_response = cf_client.get_distribution_config(Id=dist_id)
            dist_config = dist_config_response['DistributionConfig']
            
            # Extract cache behaviors
            cache_behaviors = []
            if 'CacheBehaviors' in dist_config and 'Items' in dist_config['CacheBehaviors']:
                for cb in dist_config['CacheBehaviors']['Items']:
                    cache_behaviors.append({
                        'PathPattern': cb['PathPattern'],
                        'MinTTL': cb.get('MinTTL'),
                        'MaxTTL': cb.get('MaxTTL'),
                        'DefaultTTL': cb.get('DefaultTTL'),
                        'AllowedMethods': [m['Method'] for m in cb['AllowedMethods']['Items']],
                        'CachedMethods': [m['Method'] for m in cb['CachedMethods']['Items']],
                        'ForwardedQueryStrings': cb['ForwardedValues']['QueryString'],
                        'ForwardedCookies': cb['ForwardedValues']['Cookies']['Forward']
                    })
            
            # Extract origins
            origins = []
            if 'Origins' in dist_config and 'Items' in dist_config['Origins']:
                for origin in dist_config['Origins']['Items']:
                    origins.append({
                        'Id': origin['Id'],
                        'DomainName': origin['DomainName'],
                        'CustomHeaders': origin.get('CustomHeaders', {}).get('Items', [])
                    })

            # Get CloudWatch metrics
            metrics = {}
            metric_names = ['Requests', 'BytesDownloaded', 'CacheHitRate', 'ErrorRate']
            for metric_name in metric_names:
                metric_response = cw_client.get_metric_statistics(
                    Namespace='AWS/CloudFront',
                    MetricName=metric_name,
                    Dimensions=[
                        {
                            'Name': 'DistributionId',
                            'Value': dist_id
                        },
                        {
                            'Name': 'Region',
                            'Value': 'Global' # CloudFront metrics are global
                        }
                    ],
                    StartTime=seven_days_ago,
                    EndTime=today,
                    Period=604800, # 7 days
                    Statistics=['Average']
                )
                avg_value = 0
                if metric_response['Datapoints']:
                    avg_value = metric_response['Datapoints'][0]['Average']
                metrics[metric_name] = f"{avg_value:.2f}"
            
            distributions_data.append({
                'DistributionId': dist_id,
                'DomainName': dist_summary['DomainName'],
                'Status': dist_summary['Status'],
                'Enabled': dist_summary['Enabled'],
                'PriceClass': dist_config['PriceClass'],
                'Origins': origins,
                'DefaultCacheBehavior': {
                    'MinTTL': dist_config['DefaultCacheBehavior'].get('MinTTL'),
                    'MaxTTL': dist_config['DefaultCacheBehavior'].get('MaxTTL'),
                    'DefaultTTL': dist_config['DefaultCacheBehavior'].get('DefaultTTL'),
                    'AllowedMethods': [m['Method'] for m in dist_config['DefaultCacheBehavior']['AllowedMethods']['Items']],
                    'CachedMethods': [m['Method'] for m in dist_config['DefaultCacheBehavior']['CachedMethods']['Items']],
                    'ForwardedQueryStrings': dist_config['DefaultCacheBehavior']['ForwardedValues']['QueryString'],
                    'ForwardedCookies': dist_config['DefaultCacheBehavior']['ForwardedValues']['Cookies']['Forward']
                },
                'CacheBehaviors': cache_behaviors,
                'MetricsLast7Days': metrics
            })
            
    return distributions_data



def lambda_handler(event, context):
    reservation_utilization = get_reservation_utilization()
    cost_and_usage = get_cost_and_usage()
    running_instances = get_running_ec2_instances()
    
    ec2_instances_data = []
    for instance in running_instances:
        avg_cpu = get_cpu_utilization(instance['InstanceId'])
        ec2_instances_data.append({
            'InstanceId': instance['InstanceId'],
            'Description': instance['Description'],
            'AverageCPUUtilization': f"{avg_cpu:.2f}%"
        })
        
    ebs_volumes = get_ebs_volumes()
    ebs_snapshots = get_ebs_snapshots()
    s3_data = get_s3_data()
    network_topology_data = get_network_topology()
    eks_data = get_eks_data()
    rds_data = get_rds_data()
    dynamodb_data = get_dynamodb_data()
    elasticache_data = get_elasticache_data()
    efs_data = get_efs_data()
    load_balancers_data = get_load_balancers_data()
    cloudwatch_logs_data = get_cloudwatch_logs_data()
    lambda_functions_data = get_lambda_functions_data()
    elasticsearch_data = get_elasticsearch_data()
    kinesis_data = get_kinesis_data()
    sqs_data = get_sqs_data()
    sns_data = get_sns_data()
    unused_eips_data = get_unused_eips_data()
    data_transfer_costs = get_data_transfer_costs()
    cloudfront_data = get_cloudfront_data()
    
    finops_data = {
        'reservation_utilization': reservation_utilization,
        'cost_and_usage': cost_and_usage,
        'ec2_instances': ec2_instances_data,
        'ebs_volumes': ebs_volumes,
        'ebs_snapshots': ebs_snapshots,
        's3_data': s3_data,
        'network_topology': network_topology_data['VpcData'],
        'lost_nat_gateways': network_topology_data['LostNatGateways'],
        'eks_data': eks_data,
        'rds_data': rds_data,
        'dynamodb_data': dynamodb_data,
        'elasticache_data': elasticache_data,
        'efs_data': efs_data,
        'load_balancers': load_balancers_data,
        'cloudwatch_logs': cloudwatch_logs_data,
        'lambda_functions': lambda_functions_data,
        'elasticsearch_data': elasticsearch_data,
        'kinesis_data': kinesis_data,
        'sqs_data': sqs_data,
        'sns_data': sns_data,
        'unused_eips': unused_eips_data,
        'data_transfer_costs': data_transfer_costs,
        'cloudfront_data': cloudfront_data
    }
    
    # print(json.dumps(finops_data, indent=4, default=str))

    
    return finops_data
