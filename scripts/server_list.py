import socket

clic_lab_name_list = ["algiers","amman","ankara","athens","baghdad",
"beijing","beirut","berlin","bern","brasilia","brussels","bucharest","budapest",
"cairo","canberra","copenhagen","damascus","delhi","dhaka","helsinki","islamabad",
"jerusalem","kathmandu","lima","lisbon","luxembourg","minsk","ottawa","paris",
"prague","pretoria","seoul","tehran","tokyo","tripoli","vienna","warsaw"]

clic_lab_dict = dict()
for server_name in clic_lab_name_list:
  try:
    server_ip = socket.gethostbyname("%s.clic.cs.columbia.edu"%server_name)
    print "%s (%s) is online."%(server_name,server_ip)
    clic_lab_dict[server_ip] = []
  except socket.error:
    print "%s is not online."%server_name

medium_dict = dict()           
medium_dict["128.59.15.78"] = []
medium_dict["128.59.15.72"] = []
medium_dict["128.59.15.62"] = []

larger_dict = dict(clic_lab_dict)
larger_dict["128.59.19.206"] = []
larger_dict["fraser.cs.columbia.edu"] = []
