import pulumi
import ipaddress
import pulumi_aws as aws_tf
from pulumi_command import local

class VPC:
   def __init__(self, name, cidr="10.0.0.0/16", azs=[], parent=None):
       self.name = name
       self.cidr = cidr
       self.parent = parent
       self.create_vpc()
       new_prefix = int(cidr.split("/")[1])+2
       self.azs = azs
       self.subnet_cidr = list(ipaddress.ip_network(cidr).subnets(new_prefix=new_prefix))

   def create_vpc(self):
       tags = {
         "Name": self.name
       }
       self.vpc = aws_tf.ec2.Vpc(
           f"vpc-{self.name}",
           cidr_block=self.cidr,
           enable_dns_hostnames=True,
           enable_dns_support=True,
           opts=pulumi.ResourceOptions(parent=self.parent),
           tags=tags
       )

   def get_vpc_id(self):
       return self.vpc.id

   def get_subnet_ids(self):
       return [self.subnets["subnet-private-0"].id, self.subnets["subnet-private-1"].id]

   def create_subnets(self):
       subnets_map = {
         f"subnet-public-0": 0,
         f"subnet-public-1": 1,
         f"subnet-private-0": 2,
         f"subnet-private-1": 3,
       }
       self.subnets = {}

       for name, index in subnets_map.items():
           self.subnets[name] = aws_tf.ec2.Subnet(
               name + f"-{self.name}",
               vpc_id=self.vpc.id,
               cidr_block=self.subnet_cidr[index].with_prefixlen,
               availability_zone=self.azs[index % 2],
               opts=pulumi.ResourceOptions(parent=self.vpc),
               map_public_ip_on_launch=(name.startswith("subnet-public-")),
               tags={"Name": name + f"-{self.name}"},
           )

   def create_nat_gateway(self):
       tags = {
         "Name": self.name
       }
       nat_eip = aws_tf.ec2.Eip(f"vpc-eip-{self.name}",
           opts = pulumi.ResourceOptions(parent=self.parent),
	   tags = tags,
       )
       self.nat_gw = aws_tf.ec2.NatGateway(f"vpc-nat-gw-{self.name}",
           allocation_id=nat_eip.id,
           subnet_id=self.subnets["subnet-public-0"],
	   tags = tags,
           opts = pulumi.ResourceOptions(parent=nat_eip)
       )

   def create_internet_gateway(self):
       self.igw = aws_tf.ec2.InternetGateway(f"vpc-igw-{self.name}",
                                                vpc_id=self.vpc.id,
                                                opts=pulumi.ResourceOptions(parent=self.parent))

   def create_route_table(self, table_type):
       tags = {
         "Name": f"vpc-rt-{table_type}-{self.name}",
       }

       nat_gateway_id = self.nat_gw.id if table_type == "private" else None
       gateway_id = self.igw.id if table_type == "public" else None

       rt = aws_tf.ec2.RouteTable(f"vpc-rt-{table_type}-{self.name}",
                                        vpc_id=self.vpc.id,
                                        opts=pulumi.ResourceOptions(parent=self.vpc),
                                        tags=tags,
                )

       aws_tf.ec2.Route(f"vpc-rt-r-{table_type}-{self.name}",
                                 route_table_id=rt.id,
                                 destination_cidr_block="0.0.0.0/0",
                                 gateway_id=gateway_id,
                                 nat_gateway_id=nat_gateway_id,
                                 opts=pulumi.ResourceOptions(parent=rt)
       )

       aws_tf.ec2.RouteTableAssociation(f"vpc-rt-assoc-{table_type}-{self.name}-1",
                                        subnet_id=self.subnets[f"subnet-{table_type}-0"],
                                        route_table_id=rt.id,
                                        opts=pulumi.ResourceOptions(parent=rt)
       )

       aws_tf.ec2.RouteTableAssociation(f"vpc-rt-assoc-{table_type}-{self.name}-2",
                                        subnet_id=self.subnets[f"subnet-{table_type}-1"],
                                        route_table_id=rt.id,
                                        opts=pulumi.ResourceOptions(parent=rt)
       )
       return rt

   def create_route_tables(self):
       self.public_rt = self.create_route_table("public")
       self.private_rt = self.create_route_table("private")

   def get_private_rt_table_id(self):
       return self.private_rt.id

def create_vpc(null_vpc, cidr=""):
    vpc = VPC(f"private-{region}-{pool_id}", azs=azs, parent=null_vpc, cidr=cidr)
    vpc.create_subnets()
    vpc.create_internet_gateway()
    vpc.create_nat_gateway()
    vpc.create_route_tables()
    return vpc

class TGW(pulumi.ComponentResource):
   def __init__(self, name, description='vpc', vpc_id="", subnet_ids=[], route_table_id="", cidrs=[], opts=None):
       super().__init__('custom-aws:tgw', name, None, opts)
       self.tgw = aws_tf.ec2transitgateway.TransitGateway(name,
                                                     description=description,
                                                     auto_accept_shared_attachments="enable",
                                                     default_route_table_association="disable",
                                                     default_route_table_propagation="disable",
                                                     opts=pulumi.ResourceOptions(parent=self),
                                                    )
       self._create_vpc_attachment(vpc_id, subnet_ids)
       self._create_route_table()
       self._create_vpc_route(route_table_id, cidrs)

       self.register_outputs({
           'id': self.tgw.id,
           'rt_id': self.rt.id,
       })
       self.id = self.tgw.id
       self.rt = self.rt.id


   def _create_vpc_attachment(self, vpc_id, subnet_ids):
       self.tgw_attach = aws_tf.ec2transitgateway.VpcAttachment(
           f"{self.tgw._name}-vpc-attachment",
           subnet_ids=subnet_ids,
           transit_gateway_id=self.tgw.id,
           vpc_id=vpc_id,
           opts=pulumi.ResourceOptions(parent=self.tgw)
       )

   def _create_route_table(self):
       self.rt = aws_tf.ec2transitgateway.RouteTable(
           f"{self.tgw._name}-route-table",
           transit_gateway_id=self.tgw.id,
           tags={
               "Name": f"{self.tgw._name}-route-table"
           },
           opts=pulumi.ResourceOptions(parent=self.tgw)
       )
       aws_tf.ec2transitgateway.RouteTableAssociation(f"{self.tgw._name}-route-table",
           transit_gateway_attachment_id=self.tgw_attach.id,
           transit_gateway_route_table_id=self.rt.id,
           opts=pulumi.ResourceOptions(parent=self.tgw),
       )
       aws_tf.ec2transitgateway.RouteTablePropagation(f"{self.tgw._name}-route-table",
           transit_gateway_attachment_id=self.tgw_attach.id,
           transit_gateway_route_table_id=self.rt.id,
           opts=pulumi.ResourceOptions(parent=self.tgw),
       )

   def _create_vpc_route(self, route_table_id, cidrs):
       for cidr in cidrs:
           aws_tf.ec2.Route(f"{self.tgw._name}-{cidr}",
              route_table_id=route_table_id,
              destination_cidr_block=cidr,
              transit_gateway_id=self.tgw.id,
              opts=pulumi.ResourceOptions(parent=self.tgw),
          )

class TGWATTACHMENT(pulumi.ComponentResource):
   def __init__(self, name, peer_region="", peer_transit_gateway_id="", transit_gateway_id="", route_table_id="", opts=None):
       super().__init__('custom-aws:PeeringAttachment', name, None, opts)
       self.tgw_peering = aws_tf.ec2transitgateway.PeeringAttachment(
           name,
           peer_region=peer_region,
           peer_transit_gateway_id=peer_transit_gateway_id,
           transit_gateway_id=transit_gateway_id,
           opts=pulumi.ResourceOptions(parent=self),
           tags={
               "Name": name,
           }
       )
       self._create_accepter()
       self.id = self.tgw_peering.id
       self.peering_id = self.peering.ids[0]
       self._update_route_table(route_table_id)

       self.register_outputs({
           'id': self.id,
           'peering_id': self.peering_id,
       })


   def _create_accepter(self):
       self.peering = self.tgw_peering.id.apply(
           lambda _: aws_tf.ec2transitgateway.get_peering_attachments(
               filters=[
                   {
                       "name": "transit-gateway-id",
                       "values": [self.tgw_peering.peer_transit_gateway_id],
                   },
                   {
                       "name": "state",
                       "values": ["pendingAcceptance", "available"],
                   },
               ],
           )
       )

       self.accepter = self.peering.apply(lambda p: aws_tf.ec2transitgateway.PeeringAttachmentAccepter(
           f"{self.tgw_peering._name}-accepter",
           transit_gateway_attachment_id=p.ids[0] if p.ids else "",
           opts=pulumi.ResourceOptions(parent=self.tgw_peering, ignore_changes=["transit_gateway_attachment_id"]),
       ))

   def _update_route_table(self, route_table_id):
       aws_tf.ec2transitgateway.Route(f"{self.tgw_peering._name}-staticRoute",
                                              destination_cidr_block="0.0.0.0/0",
                                              transit_gateway_attachment_id=self.peering_id,
                                              transit_gateway_route_table_id=route_table_id,
                                              opts=pulumi.ResourceOptions(parent=self.tgw_peering, depends_on=[self.accepter]),
                )


pool_id = 0
region = "us-east-1"
azs = [f"{region}a", f"{region}b"]
vpc_number = 2

tgw_ids = []
tgws = []
tgw_rts = []

for pool_id in range(vpc_number):
   vpc_cidr = f"172.31.{pool_id*16}.0/20"
   cidrs = [f"172.31.{i * 16}.0/20" for i in range(0, 6) if i != pool_id]
   
   null_vpc = local.Command(f"cmd-null-vpc-{pool_id}")
   vpc = create_vpc(null_vpc, cidr=vpc_cidr)
   
   tgw = TGW(f"tgw-vpc-{pool_id}", 
             subnet_ids=vpc.get_subnet_ids(),
             vpc_id=vpc.get_vpc_id(),
             route_table_id=vpc.get_private_rt_table_id(),
             cidrs=cidrs,
             opts=pulumi.ResourceOptions(parent=null_vpc)
            )
   tgw_ids += [tgw.id]
   tgws += [tgw.tgw_attach]
   tgw_rts += [tgw.rt]


tgw_peerings = []
tgw_peerings_accepter = []

for i in range(1, vpc_number):
    peering = TGWATTACHMENT(
        f"tgw-peering-{i}",
        peer_region="us-east-1",
        peer_transit_gateway_id=tgw_ids[i],
        transit_gateway_id=tgw_ids[0],
        route_table_id=tgw_rts[i],
        opts=pulumi.ResourceOptions(depends_on=tgws)
    )

    tgw_peerings.append(peering)
    tgw_peerings_accepter.append(peering.accepter)

#for attachment in tgw_peerings:
for i in range(1, vpc_number):
    vpc_cidr = f"172.31.{i*16}.0/20"
    aws_tf.ec2transitgateway.Route(f"staticRoute-{i}",
                                           destination_cidr_block=vpc_cidr,
                                           transit_gateway_attachment_id=tgw_peerings[i-1].id,
                                           transit_gateway_route_table_id=tgw_rts[0],
                                           opts=pulumi.ResourceOptions(depends_on=tgw_peerings_accepter),
             )


pulumi.export("tgw-rts", tgw_rts)
##pulumi.export("tgw-attach-peering-id", tgw_peering.peering_id)
