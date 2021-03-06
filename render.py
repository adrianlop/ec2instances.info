import mako.template
import mako.exceptions
import json
import datetime
import plotly
import plotly.graph_objs as go

def pretty_name(inst):
    pieces = inst['instance_type'].split('.')
    family = pieces[0]
    short  = pieces[1]
    family_names = {
        'r3': 'R3 High-Memory',
        'c3': 'C3 High-CPU',
        'c4': 'C4 High-CPU',
        'm3': 'M3 General Purpose',
        'i3': 'I3 High I/O',
        'cg1': 'Cluster GPU',
        'cc2': 'Cluster Compute',
        'cr1': 'High Memory Cluster',
        'hs1': 'High Storage',
        'c1' : 'C1 High-CPU',
        'hi1': 'HI1. High I/O',
        'm2' : 'M2 High Memory',
        'm1' : 'M1 General Purpose'
        }
    prefix = family_names.get(family, family.upper())
    extra = None
    if short.startswith('8x'):
        extra = 'Eight'
    elif short.startswith('4x'):
        extra = 'Quadruple'
    elif short.startswith('2x'):
        extra = 'Double'
    elif short.startswith('10x'):
        extra = 'Deca'
    elif short.startswith('x'):
        extra = ''
    bits = [prefix]
    if extra is not None:
        bits.extend([extra, 'Extra'])
        short = 'Large'

    bits.append(short.capitalize())

    return ' '.join([b for b in bits if b])


def network_sort(inst):
    perf = inst['network_performance']
    network_rank = [
        'Very Low',
        'Low',
        'Low to Moderate',
        'Moderate',
        'High',
        '10 Gigabit'
        ]
    try:
        sort = network_rank.index(perf)
    except ValueError:
        sort = len(network_rank)
    sort *= 2
    if inst['ebs_optimized']:
        sort += 1
    return sort


def add_cpu_detail(i):
    try:
        i['ECU_per_core'] = i['ECU'] / i['vCPU']
    except:
        # these will be instances with variable/burstable ECU
        i['ECU_per_core'] = 'unknown'


def add_vpconly_detail(i):
    # specific instances can be lanuched in VPC only
    # http://docs.aws.amazon.com/AWSEC2/latest/UserGuide/using-vpc.html#vpc-only-instance-types
    vpc_only_families = ('c4', 'm4', 't2')
    for family in vpc_only_families:
        if i['instance_type'].startswith(family):
            i['vpc_only'] = True


def add_render_info(i):
    i['network_sort'] = network_sort(i)
    i['pretty_name'] = pretty_name(i)
    add_cpu_detail(i)
    add_vpconly_detail(i)


def render(data_file, template_file, destination_file):
    """Build the HTML content from scraped data"""
    template = mako.template.Template(filename=template_file)
    print "Loading data from %s..." % data_file
    with open(data_file) as f:
        instances = json.load(f)
    for i in instances:
        add_render_info(i)
    print "Rendering to %s..." % destination_file
    generated_at = datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')
    with open(destination_file, 'w') as fh:
        try:
            fh.write(template.render(instances=instances, generated_at=generated_at))
        except:
            print mako.exceptions.text_error_template().render()

def graph(data_file, region, os):
    generated_at = datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')
    print "Loading data from %s..." % data_file
    with open(data_file) as f:
        instances = json.load(f)
    for i in instances:
        add_render_info(i)

    #Cost per type month per unit
    instance_type = []
    memory = []
    ecu = []
    disk = []
    price = []
    
    for i in instances:
        price = float(i['pricing'][region][os]['ondemand']) * 730
        instance_type.append(i['instance_type'])
        memory.append(price / i['memory'])
        if i['ECU'] == 'variable':
            ecu.append(0)
        else:
            ecu.append(price / i['ECU'])
        storage = i['storage']
        if not storage:
            disk.append(0)
        else:
            disk.append(price / ( storage['devices'] * storage['size']))
        
    trace1 = go.Bar(
        x = instance_type,
        y = ecu,
        name = "Cost Per Month Per ECU Unit"
    )

    trace2 = go.Bar(
        x = instance_type,
        y = memory,
        name = "Cost Per Month Per 1GB Memory"
    )

    trace3 = go.Bar(
        x = instance_type,
        y = disk,
        name = "Cost Per Month Per 1GB Disk"
    )

    data = [trace1, trace2, trace3]
    layout = go.Layout(
        barmode='group',
        title='Costings per type per month per unit for ondemand ' + os + ' in ' + region + ' (data by ec2instances.info generated at ' + generated_at + ')',
        yaxis = dict(
            title='USD'
        ),
        xaxis = dict(
            title='Instance Type'
        ),
    )
    fig = go.Figure(data=data, layout=layout)
    plot_url = plotly.offline.plot(fig, filename='aws-costings')
    
if __name__ == '__main__':
    render('www/instances.json', 'in/index.html.mako', 'www/index.html')
    graph('www/instances.json','us-east-1','linux')
