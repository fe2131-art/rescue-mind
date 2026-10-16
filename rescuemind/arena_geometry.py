"""Check idealized segment clearance from known station bounding boxes.

This is only a static 2-D sanity check, not contact physics or real collision risk.
"""
from math import hypot

def distance_to_rect(x,y,rect):
    xlo,xhi,ylo,yhi=rect
    return hypot(max(xlo-x,0,x-xhi),max(ylo-y,0,y-yhi))

def check_route(goals, robot_radius=.27, clearance=.02, interval=.01):
    stations={
       'water':(2-.45,2+.45,2-.45,2+.45),
       'medicine':(-2-.45,-2+.45,2-.45,2+.45),
       'shelter_B':(3-.50,3+.50,-2-.40,-2+.40),
    }
    prev=(0.,0.);minimum={k:float('inf') for k in stations}
    for goal in goals:
        length=hypot(goal[0]-prev[0],goal[1]-prev[1]);steps=max(1,int(length/interval)+1)
        for i in range(steps+1):
            u=i/steps
            x=prev[0]+u*(goal[0]-prev[0]);y=prev[1]+u*(goal[1]-prev[1])
            for k,r in stations.items():
                minimum[k]=min(minimum[k],distance_to_rect(x,y,r))
        prev=goal
    return {'kind':'static_2d_approximation_not_gazebo_collision_test',
            'minimum_clearance_m':{k:round(v,4) for k,v in minimum.items()},
            'robot_radius_assumed_m':robot_radius,
            'margin_m':clearance,
            'safe_in_approximation':all(v>robot_radius+clearance for v in minimum.values())}
