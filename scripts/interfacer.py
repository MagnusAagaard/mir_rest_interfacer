#!/usr/bin/python3
import sys
import rospy
from std_msgs.msg import String
import datetime
from time import sleep
from random import randint

import requests
import json

class MirRestInterfacer:
    def __init__(self):
        self.__init_headers()
        self.__init_params()
        # MiR state_id
        self.state_id = 0
        self.mission_group_guid = self.get_mission_group()
        self.missions_guid = self.get_missions()

    def __init_headers(self):
        self.headers = {}
        self.headers['Content-Type'] = 'application/json'
        # Authorization is generated as: BASE64(<username>:SHA-256(<password>)) for the mir.com login
        self.headers['Authorization'] = 'Basic ZGlzdHJpYnV0b3I6NjJmMmYwZjFlZmYxMGQzMTUyYzk1ZjZmMDU5NjU3NmU0ODJiYjhlNDQ4MDY0MzNmNGNmOTI5NzkyODM0YjAxNA=='

    def __init_params(self):
        # IP address of MiR Robot
        self.ip = rospy.get_param('~mir_ip','')
        if not self.ip:
            rospy.logerr('Parameter \'mir_ip\' is not provided.')
            sys.exit(-1)
        self.host = 'http://' + self.ip + '/api/v2.0.0/'

    def run(self):
        self.get_status()
        # If we ready for new mission state_id = 3 -- when executing state_id = 5
        if self.state_id == 3:
            mission = self.missions_guid[randint(0,len(self.missions_guid)-1)]
            self.post_mission(mission)
            #log mission?

    def get_status(self):
        get_status = requests.get(self.host + 'status', headers=self.headers)
        if get_status.status_code == 200:
            json_response = get_status.json()
            self.state_id = json_response.get('state_id')
            # Check e-stop or manual control initiated
            if self.state_id == 10 or self.state_id == 11:
                rospy.logwarn('Emergency stop/manual control engaged')
            # Check for error and reset if we need to
            if self.state_id == 12:
                err = json_response.get('errors')[0].get('description')
                j = json.loads(err)
                rospy.logwarn('Error occured: {}'.format(j.get('message') % j.get('args')))
                rospy.loginfo('Clearing error automatically')
                self.clear_error()
        else:
            rospy.loginfo('ERROR {}. Could not get status..'.format(get_status.status_code))

    def put_status(self, state_id):
        json_body = {'state_id' : state_id}
        put_status = requests.put(self.host + 'status', json=json_body, headers=self.headers)
        if put_status.status_code == 200:
            rospy.loginfo('Succesfully changed state_id to {}'.format(state_id))
        else:
            rospy.loginfo('ERROR: {}. Could not complete PUT request for changing state_id to {}'.format(put_status.status_code, state_id))

    def update_time(self):
        time = datetime.datetime.now(datetime.timezone.utc).isoformat().split('+')[0]
        json_body = {'datetime' : time}
        put_status = requests.put(self.host + 'status', json=json_body, headers=self.headers)
        rospy.loginfo(f'Updated time to {time}, sleeping for 10 sec. for MiR to configure itself with new time..')
        sleep(10)
        rospy.loginfo('Done sleeping!')

    def clear_error(self):
        json_body = {'clear_error' : True}
        put_status = requests.put(self.host + 'status', json=json_body, headers=self.headers)
        if put_status.status_code == 200:
            rospy.loginfo('Succesfully cleared error')
        else:
            rospy.loginfo('ERROR: {}. Could not complete PUT request for clearing error')

    def get_mission_group(self):
        mission_group = ''
        get_group = requests.get(self.host + 'mission_groups', headers=self.headers)
        if get_group.status_code == 200:
            json_response = get_group.json()
            for group in json_response:
                if group.get('name') == 'DIREC':
                    mission_group = group.get('guid')
        else:
            rospy.logerr('Could not get mission group for name \'\'.. Exiting')
            rospy.signal_shutdown()
        return mission_group

    def get_missions(self):
        missions_guid = []
        get_missions = requests.get(self.host + f'mission_groups/{self.mission_group_guid}/missions', headers=self.headers)
        
        if get_missions.status_code == 200:
            missions = get_missions.json()
            for mission in missions:
                missions_guid.append(mission.get('guid'))
        else:
            rospy.logwarn('Could not get missions')
        return missions_guid

    def post_mission(self, mission_id):
        # Maybe change this to == 4?
        if self.state_id != 3:
            self.put_status(3)
        json_body = {'mission_id': mission_id}
        post_mission = requests.post(self.host + 'mission_queue', json=json_body, headers=self.headers)
        if post_mission.status_code != 201:
            rospy.loginfo('ERROR: {}. Could not complete POST request for room with mission id: {}'.format(post_mission.status_code, mission_id))
        else:
            self.current_mission_id = post_mission.json().get('id')
            rospy.loginfo('POST request completed, mission added to queue. ID: {}'.format(self.current_mission_id))

def main():
    rospy.init_node('mir_rest_interfacer', log_level=rospy.INFO)
    r = rospy.Rate(1)
    mri = MirRestInterfacer()
    while not rospy.is_shutdown():
        mri.run()
        r.sleep()

if __name__ == "__main__":
    main()