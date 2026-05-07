import json
base = {"pressure":2.1,"temperature":40,"voltage":3.0,"leak":False,"active":True,
        "normal_interval":5,"normal_packet_count":5,"normal_packet_interval":100,
        "leak_packet_count":5,"leak_packet_interval":50}
tires = {
    "FL": {**base,"d2":"01","d3":"66","d4":"66"},
    "RL": {**base,"d2":"02","d3":"77","d4":"77"},
    "FR": {**base,"d2":"03","d3":"88","d4":"88"},
    "RR": {**base,"d2":"04","d3":"99","d4":"99"},
}
patterns = {str(i):{"name":f"Pattern {i}","tires":None} for i in range(1,6)}
data = {"mode":"single","hci":"hci0","tires":tires,"patterns":patterns}
json.dump(data, open('/home/pi/vc01-rpi3/tpms_settings.json','w'), indent=2)
print("tpms_settings.json reset ok")
