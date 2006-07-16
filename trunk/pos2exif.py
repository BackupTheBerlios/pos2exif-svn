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

import math, re, datetime,xml.dom.minidom, os
import sys

debug = False

version = "0.1"
configfilename = "~/.pos2exif/pos2exif.conf"

# error constants

ERR_TIME_ZONE_NOT_SET = 1
ERR_GPX_FORMAT_INVALID = 2
ERR_NOT_ENOUGH_PARAMETERS = 3
ERR_TIME_ZONE_INVALID = 4
ERR_SYNC_TIME_FORMAT_INVALID = 5



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

# XML helper functions

def appendNodeAndText(doc,parent,element,content):
   """ append an element node with corresponding text node to parent
   
       doc:     document
       parent:  parent node to which the child will be appended
       element: name of the text node
       content: content of the text node (None -> empty node)
   """
   s = doc.createElement(element)
   if content != None:
      t = doc.createTextNode(str(content))
      s.appendChild(t)
   parent.appendChild(s)

def getChildValue(node,childname):
   """ get value of child of node with name childname
   
       return value
         None: if node exists but no text node
       raises ValueError if child does not exist
   """ 
   for ele in node.childNodes:
      if ele.nodeType == xml.dom.minidom.Node.ELEMENT_NODE:
         if childname == ele.localName:
            value = None
            for sub in ele.childNodes:
               if sub.nodeType == xml.dom.minidom.Node.TEXT_NODE:
                  return sub.nodeValue
            return value
   raise ValueError, "no such child"

def setChildValue(doc,node,childname,value):
   found = False
   for ele in node.childNodes:
      if ele.nodeType == xml.dom.minidom.Node.ELEMENT_NODE:
         if childname == ele.localName:
            # search child of element node for text nodes
            for sub in ele.childNodes:
               if sub.nodeType == xml.dom.minidom.Node.TEXT_NODE:
                  found = True
                  if value != None:
                     # set new value, if not None
                     sub.nodeValue = str(value)
                  else:
                     # remove text node, if new value *is* None
                     ele.removeChild(sub)
                  return
            
            # element node has no text child nodes
            if not found:
               # add one, if value is not None
               if value != None:
                  sub = doc.createTextNode(str(value))
                  ele.appendChild(sub)
            return
   
   # No element node with that name found
   if not found:            
      appendNodeAndText(doc,node,childname,value)

class config:

   def __init__(self,filename,rootnodename,version,defaults=None,globelements=None):
   
      if globelements == None:
         globelements = {}
         
      self.doc = None              # pointer to xml doc in memory
      self.root = None             # pointer to root element
      self.glodata = {}
      self.globelements = globelements
      self.filename = filename     # we need that when we write the tree to disk

      filename = os.path.expanduser(filename)
      try:
         # try to parse file
         self.doc = xml.dom.minidom.parse(filename)  
      except:
         # Create default tree
         self.doc = xml.dom.minidom.Document()    # empty tree
         self.root = self.doc.createElement(rootnodename)
         self.doc.appendChild(self.root)
         self.root.setAttribute("version",str(version))
    
      # Now scan the (newly created or read) tree
      # throw exeception, if root element of XML files is not the one we expect
      
      self.root = self.doc.getElementsByTagName(rootnodename)
      assert self.root != None
      self.root = self.root[0]    # As this is the root element, only one can be available

      # check data version
      v = self.root.getAttribute("version")
      if (v != None) and (int(v) != version):
         raise ValueError,"data version not compatible"

      # populate sub-tree with defaults, if nodes are not already present
      if defaults:
         self.dict2tree(defaults, overwrite = False)
      # fill local dictionary with (merged) data from the tree
      self.glodata = self.tree2dict(globelements)

      if debug:
         print self.glodata
       
   def dict2tree(self,di, overwrite):
      if not di:
         return
         
      for key in di:
         nodelist = self.root.getElementsByTagName(key)
         nodecnt = len(nodelist)
         if nodecnt == 0:
             setChildValue(self.doc,self.root,key,di[key])
         elif nodecnt == 1:
             if overwrite:
                setChildValue(self.doc,self.root,key,di[key])
         else:
             raise ValueError,"unique key found more than once"
             
   def tree2dict(self,nodes):
      if not nodes:
         return {}
       
      di = {}
      for nodename in nodes:
         nodelist = self.root.getElementsByTagName(nodename)
         nodecnt = len(nodelist)
         if nodecnt == 1:
             val = getChildValue(self.root,nodename)  # remember, values are always strings!
             if val != None:
                if nodes[nodename] != None:           # use supplied conversion function
                   di[nodename] = nodes[nodename](val)
                else:
                   di[nodename] = val
             else:                                    # None remains None, regardless of the conversion function
                di[nodename] = None
                
         elif nodecnt == 0:
             pass
         else:
             raise ValueError,"unique key found more than once"
      return di
     
             
   def writedata(self,filename = None):
      assert self.doc != None
      out = filename
      if out == None:
         out = self.filename
      assert out != None
      
      out = os.path.expanduser(out)

      # create subdir, if necessary
      pa = os.path.split(out)[0]           # dir part
      if pa:
        if not os.path.exists(pa):
            os.makedirs(pa)
      
      # merge local dictionary into XML tree
      self.dict2tree(self.glodata, overwrite = True)
      if debug:
         print self.doc.toxml()
      fl = open(out,"w")
      fl.write(self.doc.toxml())     
#      xml.dom.ext.PrettyPrint(self.doc,fl)
      fl.close()

   def setsync(self,model,dif,time):
      found = False
      tzs = self.root.getElementsByTagName("syncoffset")
      for ele in tzs:
         mod = ele.getAttribute("model")
         if mod == model:
            found = True
            setChildValue(self.doc,ele,"diff",dif)
            setChildValue(self.doc,ele,"time",time)
            break
      
      if not found:
         ele = self.doc.createElement("syncoffset")
         ele.setAttribute("model",model)
         self.root.appendChild(ele)
         setChildValue(self.doc,ele,"diff",dif)
         setChildValue(self.doc,ele,"time",time)
         Found = True
         
      print "sync offset for %s set to %s" % (model,dif)
         
   def getsync(self,model):
      found = False
      tzs = self.root.getElementsByTagName("syncoffset")
      for ele in tzs:
         mod = ele.getAttribute("model")
         if mod == model:
            found = True
            dif = int(getChildValue(ele,"diff"))
            time = decodetime(getChildValue(ele,"time"))
            return {"diff": dif, "time":time}
      return None

   def listsync(self):
      tzs = self.root.getElementsByTagName("syncoffset")
      first = True
      for ele in tzs:
         mod = ele.getAttribute("model")
         diff = int(getChildValue(ele,"diff"))
         time = getChildValue(ele,"time")
         
         if first:
            print "Model                Offset   date"
         first = False
         
         print "%20s: %5d %s" % (mod,diff,time)
         
      if first:         
         print "no entries found"
               
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


def decodearg(s):
   return float(s)
   

def getTrackPoints(fnm):
   doc = xml.dom.minidom.parse(fnm)
   root = doc.getElementsByTagName("gpx")[0]
   tracks = root.getElementsByTagName("trk")

   allpoints = []
   lastlon = None
   tlast = None
   for track in tracks:
      tracksegments = track.getElementsByTagName("trkseg")
      for segment in tracksegments:
         first = True
         trackpoints = segment.getElementsByTagName("trkpt")
         for point in trackpoints:

            # skip frist point of every 
            if not first:
               lon = float(point.getAttribute("lon"))
               lat = float(point.getAttribute("lat"))
               try:
                  ele = getChildValue(point,"ele")
                  ele = float(ele)
               except ValueError:
                  ele = None
               try:
                  timest = getChildValue(point,"time")
               except ValueError:
                  timest = None
                        
               if timest:
                  tnow = decodetime(timest)
                  allpoints.append((tnow,lon,lat,ele))
               else:
                  tnow = None
            first = False
   
   return allpoints

def getImageData(fnm):
   # TODO: sanatize fnm
   cmd = "exiftool -e -S -CreateDate -Model -GPSLongitude " + fnm
   pipe = os.popen(cmd)
   res = pipe.read()
   errno = pipe.close()
   
   retval = None
   
   if errno == None:
      retval = {}
      resl = res.splitlines()
      for line in resl:
         wp = line.split(":",1)
         tag = wp[0]
         value = wp[1].strip()
         if tag == "CreateDate":
            retval["date"] = decodetime(value)
         if tag == "Model":
            retval["model"] = value
         if tag == "GPSLongitude":
            retval["gpslon"] = value
            
   # check, if we have a valid data set
   # in case of an "Image Format Error", exiftool does NOT return an error code 
   
   try:
      x = retval["date"]
      x = retval["model"]
   except KeyError:
      retval = None
      
   return retval

def sync(fnm,rdouttime):
   imdata = getImageData(fnm)

   if debug:   
      print "Time in picture",imdata["date"], "Time in read-out:", rdouttime
   if imdata["date"] < rdouttime:
      dif = (rdouttime - imdata["date"]).seconds
   else:
      dif = -(imdata["date"] - rdouttime).seconds
         
   res = {"model": imdata["model"], "diff": dif, "date": imdata["date"]}   
   
   if debug:
      print "Sync result:", res
   return res

def lookupTrack(reftrack,time):

   maxpoi = len(reftrack)     # 0: time, 1: lon, 2: lat, 3: ele
   
   if time < reftrack[0][0]:
      return None
      
   if time > reftrack[maxpoi-1][0]:
      return None
      
   # binary search
   low = 0
   top = maxpoi -1
   mode = 0
   
   while True:
     
     test = (top+low) / 2
     if test == top:
        break
     
     if debug:
        print
        print "dest:", time
        print "Low: ",low, reftrack[low][0]
        print "High: ",top, reftrack[top][0]
        print "test: ",test, reftrack[test][0]
        print "test+1: ",test+1, reftrack[test+1][0]
     
     if reftrack[test][0] == time:
        low = test
        top = test
        break
     
     if reftrack[test+1][0] == time:
        low = test+1
        top = test+1
        break

     if (reftrack[test][0] < time) and (time < reftrack[test+1][0]):
        low = test
        top = test+1
        break

     if reftrack[test][0] < time:
        low = test
        continue

     if reftrack[test][0] > time:
        top = test
        continue
       

   if debug:
      print "Ergebnis: ", mode, low, top
      
   plow = reftrack[low]
   phigh = reftrack[top]
   if low == top:
      return plow
   
   # TODO: plausibility, ele==None, dif < 5, but time > 20 ...

   dtp = (phigh[0] - plow[0]).seconds

   if dtp == 0:
      return plow
  
   dt = (time - plow[0]).seconds

  
   mlon = (phigh[1] - plow[1]) * dt / dtp + plow[1]
   mlat = (phigh[2] - plow[2]) * dt / dtp + plow[2]
   mele = (phigh[3] - plow[3]) * dt / dtp + plow[3]

   mpoi = (time,mlon,mlat,mele)
   if debug:
      print "A: ",plow
      print "B: ",phigh
      print "M: ",mpoi
      print "Distance A/B",distance(plow[1],plow[2],phigh[1],phigh[2])
      print "time dif A/B",dtp
      print "time dif A/M",dt
   
   return mpoi     

def getPosition(track, fnm, gpsoverwrite = False):
   global conf

   imgval = getImageData(fnm)
   if imgval == None:
      print "no exif data found"
      return None
      
   if not gpsoverwrite:
      try:
         x = imgval["gpslon"]
         print "image already contains GPS data"
         return None
      except KeyError:
         pass
   imgtime = imgval["date"]
   syncdata = conf.getsync(imgval["model"])
   if syncdata == None:
      print "no sync datat for model %s" %(imgval["model"],)
      return None
      
   imgsync = syncdata["diff"]
   syncage = abs(imgtime - syncdata["time"])
   
   if debug: 
      print "Image time",imgtime
      print "Sync diff",imgsync
      print "Syncage (days)", syncage.days
      print conf.glodata
      
   if syncage.days > 30:
      print "Warning: time difference to clock sync: %s days" % (syncage.days,)
      
   dt = datetime.timedelta(hours = -conf.glodata["gpstimezone"], seconds = imgsync)
   corrtime = imgtime + dt
   po = lookupTrack(track, corrtime)
   if po == None:
      print "No suitable point found"
   return po
   
def setPosition(fnm,pos):
   lon = pos[1]
   lat = pos[2]
   alt = pos[3]
   
   if lon >= 0:
      lonR = "E"
   else:
      lonR = "W"
      lon = -lon
   
   if lat >= 0:
      latR = "N"
   else:
      latR = "S"
      lat = -lat
   
   # -P = preserve file date
   # -overwrite_original
   cmd = "exiftool -P -GPSLongitude=\"%s\" -GPSLongitudeRef=\"%s\" -GPSLatitude=\"%s\" -GPSLatitudeRef=\"%s\"" % (lon,lonR,lat,latR)
   if alt != None:
      if alt >= 0:
         altR = "Above Sea Level"
      else:
         altR = "Below Sea Level"
         alt = -alt
      cmd += " -GPSAltitude=\"%s\" -GPSAltitudeRef=\"%s\"" % (alt,altR)
   
   cmd += " \"%s\"" % (fnm,)

   if debug:
      print cmd
   
   pipe = os.popen(cmd)
   res = pipe.read()
   errno = pipe.close()

   return (errno,res)

   
def preflightcheck():
   notz = True
   try:
      tz = conf.glodata["gpstimezone"]
      if tz != None:
         notz = False
   except KeyError:
      pass
   if notz:
      print """time zone of the GPS receiver not set.
use 
   pos2exif gpstz #
"""
      sys.exit(ERR_TIME_ZONE_NOT_SET)
          

def usage():
   print "pos2exif, version", version, "Copyright 2006, Michael Strecke"
   print """"pos2exif comes with ABSOLUTELY NO WARRANTY"

Available commands:

gpstz #                               set time zone used in GPS receiver display (numerical value)
sync filename JJJJ.MM.TT HH:MM:SS     determine time difference between GPS clock and the clock in digital camera
listsync                              display all sync data
gpstag gpxfile image                  store GPS data derived from track in .GPX file in the EXIF data of the image
gpstagovr gpxfile filename            same as "gpstag", but overwrites existing GPS data
help                                  This message
"""

def do_gpstz(dz):
   try:
      w = int(dz)
   except ValueError:
      print "numerical values only"
      
   conf.glodata["gpstimezone"] = w
   print "GPS time zone set to", w
   
def do_sync(fnm,d,h):
   try:
      rdouttime = decodetime(d + " " + h)
   except ValueError:
      print "enter time in the following format: JJJJ.MM.TT HH:MM:SS"
      return
      
   res = sync(fnm,rdouttime)
   conf.setsync(res["model"],res["diff"],res["date"])

def do_gpstag(gpx,filelist, overwrite = False):
   print "Reading track file:",gpx
   try:
      reftrack = getTrackPoints(gpx)
   except xml.parsers.expat.ExpatError:
      print "unsuitable gpx file"
      sys.exit(ERR_GPX_FORMAT_INVALID)
      
   print "sorting points"
   reftrack.sort()
   print "Number of usable points:",len(reftrack)

   cnterr = 0
   cntfiles = 0
   for fnm in filelist:
      print fnm
      cntfiles += 1
      w = getPosition(reftrack, fnm, gpsoverwrite = overwrite)
      if w:
         erg = setPosition(fnm,w)
         if erg[0]:
            print "Error %s\n%s\n" % erg
            cnterr += 1
      else:
         cnterr += 1
         
   if cnterr:
      print "%s files processed, %s errors" % (cntfiles, cnterr)
   else:
      print "%s files processed" % (cntfiles,)

def do_listsync():
   pass

if __name__ == "__main__":
   conf = config(configfilename,"pos2exit",1,defaults = {"gpstimezone": None},globelements = {"gpstimezone": int})

   cmdline = sys.argv

   if len(cmdline)<2:
      usage()
      sys.exit(ERR_NOT_ENOUGH_PARAMETERS)

   cmd = cmdline[1].lower()    # ignore case in command keyword

   if cmd == "gpstz":
      try:
         do_gpstz(cmdline[2])
      except IndexError:
         usage()
         sys.exit(ERR_TIME_ZONE_INVALID)
      
   if cmd == "sync":
      preflightcheck()
      try:
         do_sync(cmdline[2],cmdline[3],cmdline[4])
      except IndexError:
         usage()
         sys.exit(ERR_SYNC_TIME_FORMAT_INVALID)

   if cmd == "gpstag":
      preflightcheck()
      try:
         do_gpstag(cmdline[2], cmdline[3:], overwrite = False)
      except IndexError:
         usage()
         sys.exit(ERR_NOT_ENOUGH_PARAMETERS)

   if cmd == "gpstagovr":
      preflightcheck()
      try:
         do_gpstag(cmdline[2], cmdline[3:], overwrite = True)
      except IndexError:
         usage()
         sys.exit(ERR_NOT_ENOUGH_PARAMETERS)

   if cmd == "listsync":
      conf.listsync()
      sys.exit(0)

   if cmd == "help":
      usage()
      sys.exit(0)
   
   conf.writedata()

