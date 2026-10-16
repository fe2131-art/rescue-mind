"""Minimal validation of local ROS 2 bag metadata (not Gazebo authentication).

Post-shutdown only: ROS 2 recorder must be given SIGINT to finalize metadata.
"""
from pathlib import Path
import math

class BagEvidenceError(ValueError):
    pass

REQUIRED = ('/odom', '/cmd_vel', '/camera', '/scan', '/rescuemind/cmd_vel_request')

def audit_bag_metadata(bag_path, *, require_clock=False):
    try:
        import yaml
    except ImportError as e:
        raise BagEvidenceError('PyYAML missing') from e
    bag_path=Path(bag_path)
    doc=bag_path/'metadata.yaml'
    if not doc.is_file():
        raise BagEvidenceError('rosbag2 metadata.yaml not finalized')
    try:
        obj=yaml.safe_load(doc.read_text(encoding='utf8'))
        root=obj['rosbag2_bagfile_information']
        topics=root['topics_with_message_count']
    except (KeyError,ValueError,TypeError,yaml.YAMLError) as exc:
        raise BagEvidenceError('malformed rosbag2 metadata') from exc
    counts={}
    for item in topics:
        try:
            name=item['topic_metadata']['name']
            count=item['message_count']
        except (KeyError,TypeError) as exc:
            raise BagEvidenceError('invalid topic count schema') from exc
        if type(name) is not str or type(count) is not int or count<0 or name in counts:
            raise BagEvidenceError('invalid/duplicate rosbag2 topic row')
        counts[name]=count
    required=REQUIRED + (('/clock',) if require_clock else ())
    missing=[t for t in required if counts.get(t,0)<3]
    if missing:
        raise BagEvidenceError('required topics missing/too few messages: '+', '.join(missing))
    files=root.get('relative_file_paths',[])
    if not isinstance(files,list) or not files or any(not isinstance(f,str) or '..' in Path(f).parts or Path(f).is_absolute() for f in files):
        raise BagEvidenceError('invalid bag storage paths')
    for rel in files:
        f=bag_path/rel
        if not f.is_file() or f.stat().st_size < 100:
            raise BagEvidenceError('missing/empty bag storage file: '+rel)
    return {'pass':True,'scope':'ROS2_BAG_METADATA_ONLY_NOT_AUTHENTICATED_GAZEBO',
            'required_topic_counts':{t:counts[t] for t in required},
            'clock_domain': 'sim_time_metadata_only' if require_clock else 'unspecified',
            'bag_storage_files':files}
