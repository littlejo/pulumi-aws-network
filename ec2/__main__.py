import pulumi
import pulumi_aws as aws

this = aws.ec2.get_ami(most_recent=True,
    owners=["amazon"],
    filters=[
        {
            "name": "architecture",
            "values": ["arm64"],
        },
        {
            "name": "name",
            "values": ["al2023-ami-2023*"],
        },
    ])

deploy = aws.ec2.KeyPair("deploy",
    key_name="deploy",
    public_key="ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABgQDbn1bCFoD5oiWokQ25b6S85tPwxoUFZZHu5rcF+PtSZOzZALit2o2TmbQw7SWWw+a2Q+GWV9+ATRFq3pjEIyYd55ONNs2DOCio2xDDfDMVhFxn2+bJJQptlzgMIiXBKptcgay9d5HgRNyIyDSpf1rIUYIQHOGKo91/jPmu8X3DdYSap59sX62KvM+gwYVJFL1b4POKTCxcOYVO81PHU3uVTtQD9HZ88ISEwsZLoPdfld5Zkd1kyeEyESOIKw5q7odXOKYBU6enyOaC6J+uDnrrJ588j3iygXwB6OnZ+ibPg064VHs+AfTTRYw1H4ciBXJTGsROI6RADg6M3UG0d5NynjZHPZ5p/IjGPkpaF3YJNnuG6H/TGkq7Qs6AB5VFaq6tjhfM7e20IW3lPc9JmU/kdUXrZkxiZzt44quUyQpxcka4SX0a8NuuJFHujw+ds8ja3M3Go0qDa8G4zE/ZCwukIzJE68+duGV8/K5TInRoTZkiuetQrU+/7lvBGqxEoQM=")


def create_sg(vpc_id, a=""):
    allow_ssh = aws.ec2.SecurityGroup(f"allow_ssh{a}",
        name="allow_ssh",
        description="Allow SSH inbound traffic and all outbound traffic",
        vpc_id=vpc_id,
        tags={
            "Name": "allow_ssh",
        })
    aws.vpc.SecurityGroupIngressRule(f"allow_ssh_ipv4{a}",
        security_group_id=allow_ssh.id,
        cidr_ipv4="0.0.0.0/0",
        from_port=22,
        ip_protocol="tcp",
        to_port=22)
    aws.vpc.SecurityGroupEgressRule(f"allow_ssh_ipv4{a}",
        security_group_id=allow_ssh.id,
        cidr_ipv4="0.0.0.0/0",
        ip_protocol="-1",
                                    )
    return allow_ssh

def create_ec2(subnet_id, allow_ssh, a=""):
    this_instance = aws.ec2.Instance(f"this{a}",
        ami=this.id,
        instance_type=aws.ec2.InstanceType.T4G_NANO,
        subnet_id=subnet_id,
        key_name="deploy",
        vpc_security_group_ids=[allow_ssh.id]
    )

vpc_id = "vpc-06fe3f61362e32f92"
subnet_id = "subnet-03d4a3a299a4e535c"
allow_ssh = create_sg(vpc_id)
create_ec2(subnet_id, allow_ssh)
create_ec2("subnet-02a40587e21e65b6b", allow_ssh, a="ddd")

allow_ssh = create_sg("vpc-0fd5d5de5214942a0", a="ddd")
create_ec2("subnet-0f4bdab3a5c556488", allow_ssh, a="ccc")
create_ec2("subnet-0770aa1a7d196003a", allow_ssh, a="eee")
