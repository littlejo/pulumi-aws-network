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
    public_key="TOCHANGE")


def create_sg(vpc_id, a):
    allow_ssh = aws.ec2.SecurityGroup(f"allow_ssh{a}",
        name=f"allow_ssh{a}",
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

def create_ec2(subnet_id, allow_ssh, name):
    this_instance = aws.ec2.Instance(name,
        ami=this.id,
        instance_type=aws.ec2.InstanceType.T4G_NANO,
        subnet_id=subnet_id,
        key_name="deploy",
        vpc_security_group_ids=[allow_ssh.id]
    )
    return this_instance

def get_vpc_id(cidr):
    vpc = aws.ec2.get_vpc(cidr_block=cidr)
    return vpc.id

def get_subnet_id(vpc_id, subnet_type, subnet_id=0):
    subnet = aws.ec2.get_subnet(vpc_id=vpc_id, tags={"Name": f"subnet-{subnet_type}-1-*"})
    return subnet.id

def create_bastion(cidr):
    vpc_id = get_vpc_id(cidr)
    public_subnet_id = get_subnet_id(vpc_id, "public")
    allow_ssh = create_sg(vpc_id, "bastion")
    public_instance = create_ec2(public_subnet_id, allow_ssh, "public_instance")
    return public_instance.public_ip

def create_instance(cidr, vpc_name):
    vpc_id = get_vpc_id(cidr)
    subnet_id = get_subnet_id(vpc_id, "private")
    allow_ssh = create_sg(vpc_id, vpc_name)
    private_instance = create_ec2(subnet_id, allow_ssh, f"private_instance{vpc_name}")
    return private_instance.private_ip

cidrs = [
        "172.31.0.0/20",
        "172.31.16.0/20",
        "172.31.32.0/20",
        "172.31.48.0/20",
        "172.31.64.0/20",
        ]

public_ip = create_bastion(cidrs[0])
ip1 = create_instance(cidrs[0], "1")
ip2 = create_instance(cidrs[1], "2")
ip3 = create_instance(cidrs[2], "3")

pulumi.export("public_ip", public_ip)
pulumi.export("ip1", ip1)
pulumi.export("ip2", ip2)
pulumi.export("ip3", ip3)
