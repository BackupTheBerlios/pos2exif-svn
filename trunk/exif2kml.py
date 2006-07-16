#!/usr/bin/env python
#
# pos2exif - store GPS data in EXIF data field
#
# Copyright (C) 2006  Michael Strecke
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
#


import sys, os, re, datetime, math, cgi

version = "0.1"
maxradius = 45
maxpics = 6

# Convert functions

def decodetime(s):
   # 2006-07-07T10:20:56Z
   erg = re.match("^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})Z$",s)
   if erg:
      return datetime.datetime(int(erg.group(1)),int(erg.group(2)),int(erg.group(3)),int(erg.group(4)),int(erg.group(5)),int(erg.group(6)))   

   # 2006:07:07 17:06:38 or 2006.07.07 17:06:38 or 2006-07-07 17:06:38
   # JJJJ:MM:DD HH:MM:SS
   erg = re.match("^(\d{4})[:|.|-](\d{2})[:|.|-](\d{2}) (\d{2}):(\d{2}):(\d{2})$",s)
   if erg:
      return datetime.datetime(int(erg.group(1)),int(erg.group(2)),int(erg.group(3)),int(erg.group(4)),int(erg.group(5)),int(erg.group(6)))   

   raise ValueError,"Unknow date format: "+s

def distance(longS, latS, longD, latD):
   # http://obivan.uni-trier.de/p/h/vb/third_b_va.html
   radius = 6370000.0
   tobog = math.pi / 180.0
   dl = abs(longS - longD) * tobog
   
   latS *= tobog
   latD *= tobog
   
   cos_d = math.sin(latS) * math.sin(latD) + math.cos(latS) * math.cos(latD) * math.cos(dl)
   dist = math.acos(cos_d) * radius 
   
   return dist

def getImageData(fnm):
   # TODO: sanatize fnm
   cmd = "exiftool -e -S -c \"%%.10f\" -GPSLongitude -GPSLongitudeRef -GPSLatitude -GPSLatitudeRef -GPSAltitude -GPSAltitudeRef -CreateDate \"%s\"" % (fnm,)
   pipe = os.popen(cmd)
   res = pipe.read()
   errno = pipe.close()
   
   alt = 0
   altfac = 1
   lat = None
   latfac = 1
   lon = None
   lonfac = 1
   crea = None
   
   if errno == None:
      resl = res.splitlines()
      for line in resl:
         wp = line.split(":",1)
         tag = wp[0]
         value = wp[1].strip()

         if tag == "GPSLongitude":
            try:
               lon = float(value)
            except ValueError:
               lon = None

         if tag == "GPSLongitudeRef":
            if value == "West":
              lonfac = -1

         if tag == "GPSLatitude":
            try:
               lat = float(value)
            except ValueError:
               lat = None

         if tag == "GPSLatitude":
            if value == "South":
              latfac = -1

         if tag == "GPSAltitude":
            try:
               alt = float(value.split(" ")[0])
            except ValueError:
               alt = 0

         if tag == "GPSAltitudeRef":
            if value == "Below Sea Level":
              altfac = -1
         
         if tag == "CreateDate":
            crea = decodetime(value)

   if lon==None or lat == None or crea == None:
      raise ValueError,"data incomplete"

   return (crea, lat * latfac, lon * lonfac, alt * altfac,os.path.basename(fnm))

""" Simple Format
<?xml version="1.0" encoding="UTF-8"?>
<Document xmlns:xlink="http://www.w3/org/1999/xlink">
   <name>Bildinfo</name>
   <visibility>1</visibility>
   <Folder>
      <visibility>1</visibility>
      <open>1</open>
      <name>Waypoints</name>
      <Placemark> 
         <name>Bild_2182</name>
         <description>Hier steht eine Beschreibung drin</description>
         <Point>
            <coordinates>5.49785,50.60531111,62,5269</coordinates>
         </Point>
      </Placemark>
   </Folder>
</Document>

<description><![CDATA[ html text ]]></description>
"""

def outputgrouplist(dev,liste,startname,startzeit,endname,endzeit,maxpics):
   num = len(liste)
   if num == 0:
      return
      
   sumlon = 0
   sumlat = 0
   sumele = 0
   for p in liste:
      sumlon += p[2]
      sumlat += p[1]
      sumele += p[3]
   
   sumlon /= num
   sumlat /= num
   sumele /= num
   
   if num == 1:
      name = startname
      description = "Picture %s<br>%s" % (startname,startzeit)
   else:
      name = "%s (%s)" % (startname,num)
      description = "<b>%s pictures</b><br>%s -<br>%s<br>" % (num,startzeit,endzeit)
      
      for p in range(min(num,maxpics-1)):
         description += "%s<br>" % (cgi.escape(liste[p][4]),)
      if num > maxpics:
         description += "...<br>"
      if num >= maxpics:
         description += "%s<br>" % (cgi.escape(liste[num-1][4]),)
      
   
   dev.write("<Placemark>\n<name>%s</name>\n<description><![CDATA[%s]]></description>\n" % (name, description))
   dev.write("<Point><coordinates>%s,%s,%s</coordinates></Point>\n</Placemark>\n" % (sumlon,sumlat,sumele))

def remainingpointswithindistance(liste,meanlon,meanlat,max):
   """ check if all points in the point list are within a max. radius around the median point
   """
   for p in liste:
      if distance(p[2],p[1],meanlon,meanlat) > max:
         return False
   return True

def outputkml(liste,fnm,maxdist,maxpics):
   fnm = os.path.expanduser(fnm)
   f = open(fnm,"w")
   f.write( """<?xml version="1.0" encoding="UTF-8"?>
<Document xmlns:xlink="http://www.w3/org/1999/xlink">
   <name>picture pos</name>
   <visibility>1</visibility>
   <Folder>
      <visibility>1</visibility>
      <open>1</open>
      <name>Photos</name>
""")

   grouplist = []
   groupcnt = 0
   lonsum = 0
   latsum = 0
   startname = None
   endname = None
   starttime = None
   endtime = None
   
   for pos in liste:

      addtolist = False
      
      if groupcnt == 0:
         startname = pos[4]
         starttime = pos[0]
         addtolist = True
      else:
         lonsum += pos[2]
         latsum += pos[1]
         dist = distance(pos[2],pos[1],lonsum / (groupcnt + 1),latsum / (groupcnt + 1))
         if dist < maxdist:
            addtolist = True
            if groupcnt > 1:
               if remainingpointswithindistance(grouplist, lonsum / (groupcnt + 1),latsum / (groupcnt + 1),maxdist):
                  addtolist = True

      if addtolist:
         endname = pos[4]
         endtime = pos[0]
         grouplist.append(pos)
         groupcnt += 1
      else:
         outputgrouplist(f,grouplist,startname,starttime,endname,endtime,maxpics)
         grouplist = []
         startname = pos[4]
         starttime = pos[0]
         lonsum = pos[2]
         latsum = pos[1]
         grouplist.append(pos)
         groupcnt = 1
            
   outputgrouplist(f,grouplist,startname,starttime,endname,endtime,maxpics)

   f.write("""   </Folder>
</Document>
""")
   f.close()


cnt = 0
imlist = []
fnmlist = sys.argv[1:]
for fnm in fnmlist:
  print fnm
  try:
     po = getImageData(fnm)
     cnt += 1
  except ValueError:
     po = None
  if po:
     imlist.append(po)
  else:
     print "No data"

print "%s data points found" % (cnt,)

print "Sorting list"
imlist.sort()

print "Writeing KML file"

outputkml(imlist,"~/Desktop/pics.kml",maxradius,maxpics)
