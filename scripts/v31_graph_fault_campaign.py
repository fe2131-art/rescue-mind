#!/usr/bin/env python3
"""Deterministic publisher takeover campaign; synthetic endpoint objects, NOT ROS live."""
from pathlib import Path
import json,sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from rescuemind.runtime_guard_graph import RuntimeGuardGraph, GraphMonitorFault
GOOD_CMD=[{'node_name':'rescuemind_velocity_guard','node_namespace':'/','topic_type':'geometry_msgs/msg/Twist'}]
GOOD_READY=[{'node_name':'rescuemind_velocity_guard','node_namespace':'/','topic_type':'std_msgs/msg/Bool'}]
rogue={**GOOD_CMD[0],'node_name':'unapproved_node'}
wrong_type={**GOOD_CMD[0],'topic_type':'std_msgs/msg/String'}
wrong_ns={**GOOD_CMD[0],'node_namespace':'/unexpected'}
CASES=[
 ('sole_guard',GOOD_CMD,GOOD_READY,True),
 ('another_cmd_publisher',GOOD_CMD+[rogue],GOOD_READY,False),
 ('duplicate_guard_cmd_publishers',GOOD_CMD+GOOD_CMD,GOOD_READY,False),
 ('cmd_guard_missing',[],GOOD_READY,False),
 ('guard_status_missing',GOOD_CMD,[],False),
 ('cmd_wrong_type',[wrong_type],GOOD_READY,False),
 ('cmd_wrong_namespace',[wrong_ns],GOOD_READY,False),
 ('guard_status_wrong_type',GOOD_CMD,[{**GOOD_READY[0],'topic_type':'geometry_msgs/msg/Twist'}],False),
 ('guard_status_wrong_namespace',GOOD_CMD,[{**GOOD_READY[0],'node_namespace':'/wrong'}],False),
 ('guard_status_intruder',GOOD_CMD,GOOD_READY+[{**GOOD_READY[0],'node_name':'intruder'}],False),
 ('both_topics_empty',[],[],False),
 ('cmd_only',GOOD_CMD,[],False),
 ('status_only',[],GOOD_READY,False),
 ('cmd_invalid_endpoint',[{'node_name':'unknown'}],GOOD_READY,False),
 ('guard_status_invalid_endpoint',GOOD_CMD,[{'node_name':'unknown'}],False),
 ('cmd_rogue_no_valid_guard',[rogue],GOOD_READY,False),
]
results=[]
for title,cmd,status,expected in CASES:
    m=RuntimeGuardGraph(0,startup_grace_s=2)
    assert m.observe(.3,GOOD_CMD,GOOD_READY)=='sole_guard_confirmed'
    try:
        m.observe(.6,cmd,status)
        actual=True;latched=False
    except GraphMonitorFault:
        actual=False;latched=m.latched is not None
    if actual!=expected or (not expected and not latched):
        raise RuntimeError('fault campaign mismatch: '+title)
    results.append({'case':title,'expected_allow':expected,'actual_allow':actual,'fault_latched':latched})
report={'scope':'SYNTHETIC_ROS_GRAPH_ENDPOINTS_ONLY','tested':len(results),
        'matched':sum(x['expected_allow']==x['actual_allow'] for x in results),
        'all_matched':True,'results':results,'real_ROS_tested':False}
out=ROOT/'verification/v31/graph_fault_campaign.json';out.parent.mkdir(parents=True,exist_ok=True)
out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'tested':report['tested'],'matched':report['matched'],'scope':report['scope']}))
