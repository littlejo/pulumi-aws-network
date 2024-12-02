import pulumi
import pulumi_aws as aws



def create_sg(vpc_id, aws_provider, a):
    allow_ssh = aws.ec2.SecurityGroup(f"allow_ssh{a}",
        name=f"allow_ssh{a}",
        description="Allow SSH inbound traffic and all outbound traffic",
        vpc_id=vpc_id,
        tags={
            "Name": "allow_ssh",
        },
        opts=pulumi.ResourceOptions(provider=aws_provider))
    aws.vpc.SecurityGroupIngressRule(f"allow_ssh_ipv4{a}",
        security_group_id=allow_ssh.id,
        cidr_ipv4="0.0.0.0/0",
        from_port=22,
        ip_protocol="tcp",
        to_port=22,
        opts=pulumi.ResourceOptions(provider=aws_provider))
    aws.vpc.SecurityGroupEgressRule(f"allow_ssh_ipv4{a}",
        security_group_id=allow_ssh.id,
        cidr_ipv4="0.0.0.0/0",
        ip_protocol="-1",
        opts=pulumi.ResourceOptions(provider=aws_provider))
    return allow_ssh

def create_ec2(subnet_id, allow_ssh, aws_provider, name):
    ami_id = get_ami_id(aws_provider)
    this_instance = aws.ec2.Instance(name,
        ami=ami_id,
        instance_type=aws.ec2.InstanceType.T4G_NANO,
        subnet_id=subnet_id,
        key_name="deploy",
        vpc_security_group_ids=[allow_ssh.id],
        opts=pulumi.ResourceOptions(provider=aws_provider))
    return this_instance

def get_vpc_id(cidr, aws_provider):
    vpc = aws.ec2.get_vpc(cidr_block=cidr, opts=pulumi.InvokeOptions(provider=aws_provider))
    return vpc.id

def get_subnet_id(vpc_id, subnet_type, aws_provider, subnet_id=0):
    subnet = aws.ec2.get_subnet(vpc_id=vpc_id, tags={"Name": f"subnet-{subnet_type}-1-*"}, opts=pulumi.InvokeOptions(provider=aws_provider))
    return subnet.id

def create_bastion(cidr, aws_provider):
    vpc_id = get_vpc_id(cidr, aws_provider)
    public_subnet_id = get_subnet_id(vpc_id, "public", aws_provider)
    allow_ssh = create_sg(vpc_id, aws_provider, "bastion")
    public_instance = create_ec2(public_subnet_id, allow_ssh, aws_provider, "public_instance")
    return public_instance.public_ip

def create_instance(cidr, aws_provider, vpc_name):
    vpc_id = get_vpc_id(cidr, aws_provider)
    subnet_id = get_subnet_id(vpc_id, "private", aws_provider)
    allow_ssh = create_sg(vpc_id, aws_provider, vpc_name)
    private_instance = create_ec2(subnet_id, allow_ssh, aws_provider, f"private_instance{vpc_name}")
    return private_instance.private_ip

def create_key(aws_provider, a):
    deploy = aws.ec2.KeyPair(f"deploy-{a}",
        key_name="deploy",
        public_key="TOADD",
        opts=pulumi.ResourceOptions(provider=aws_provider)
    )

def get_ami_id(aws_provider):
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
        ],
       opts=pulumi.InvokeOptions(provider=aws_provider)
       )
    return this.id

cidrs = [
        "172.31.0.0/20",
        "172.31.16.0/20",
        "172.31.32.0/20",
        "172.31.48.0/20",
        "172.31.64.0/20",
        ]

use1 = aws.Provider(f"aws-east-1", region="us-east-1")
usw2 = aws.Provider(f"aws-west-2", region="us-west-2")

create_key(use1, "aaa")
create_key(usw2, "bbb")

public_ip = create_bastion(cidrs[0], usw2)

ip1 = create_instance(cidrs[0], usw2, "1")
ip2 = create_instance(cidrs[1], use1, "2")

pulumi.export("public_ip", public_ip)
pulumi.export("ip1", ip1)
pulumi.export("ip2", ip2)
##pulumi.export("ip3", ip3)
