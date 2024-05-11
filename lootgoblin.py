
import requests
from bs4 import BeautifulSoup
import logging
import socket
import re
import parse
import os
import requests.packages.urllib3.util.connection as urllib3_cn
import argparse
import yaml
from packaging.version import Version
import time
from urllib.parse import urlparse, urljoin
from datetime import datetime
   

def allowed_gai_family():
    """
     https://github.com/shazow/urllib3/blob/master/urllib3/util/connection.py
    """
    family = socket.AF_INET
    return family

urllib3_cn.allowed_gai_family = allowed_gai_family


#TODO: Move some logic from treasury here 
class Artifact():
    def __init__(self, params, url):
        pass

    def loot(self):
        pass

    
class ISOTreasury():
    # Don't try to download urls ending with these
    # This should better go to some config file
    # FixMe: Filtering based on content-type would be better.
    blacklist = [
        ".iso",
        ".xz",
        ".img",
        "SHA256SUMS",
        "SHA512SUMS",
        ".sign",
        ".torrent",
        ".jigdo",
        ".template",
        ".msi",
        ".rpm",
        ".exe",
        ".gz",
        ".vfd"
    ]

    def _validate_params(self, params):
        #FixMe: perhaps we need proper param validation here
        pass

    def set_date_format(self, fmt):
        self.date_format = fmt

    def __init__(self, params):
        url = params["url"]
        self.maxdepth = 1
        self.recursive = False
        self.maxdate = {}
        self._validate_params(params)
        if "maxdepth" in params:
            self.recursive = True
            self.maxdepth = params["maxdepth"]
        self.pattern = params["pattern"]
        self.params = params
        for item in url:
            if not item.endswith("/"):
                item += "/"
        if type(url) is str:
            self.url = [url]
        else:
            self.url = url
        self.artifacts = []
        self.seen = []
    
    def absolute_url(self, base, ref):
        ref = urljoin(base, ref)
        ref = ref.split("?")[0]
        #sourceforge fix
        if ref.endswith("/download"):
            ref = ref.replace("/download", "")
        return ref

    def add(self, ref, fmt):
        total = 0
        match = 0
        if "consider_paths" in self.params:
            total += 1
            for p in self.params["consider_paths"]:
                if ref.find(p) >= 0:
                    match += 1
                    break

        for key, value in self.params["constraints"].items():
            total += 1

            if key == "version":
                try: 
                    #In case we parsed shit, just go on
                    the_version = Version(fmt[key])
                except:
                    continue
                    
                if not hasattr(self, "maxversion") or Version(self.maxversion) < the_version:
                    self.maxversion = fmt[key]

                if value == "latest":
                    match += 1
                    continue

            if key == "date":
                version = fmt["version"]
                mdate = datetime.strptime(fmt["date"], self.date_format);
                if not version in self.maxdate or self.maxdate[version] < mdate:
                    self.maxdate[version] = mdate

                if value == "latest":
                    match += 1
                    continue

            if key in fmt:
                if type(value) is str:
                    value = [value]
                for v in value:
                    if fmt[key] == v:
                        match += 1

        if total == match:
            self.artifacts.append(ref)

    def lurk(self, baseurl=None, url=None, depth=0):
        if url is None:
            for url in self.url:
                self.lurk(url, url)
            return

        if url in self.seen:
            return

        if depth > self.maxdepth:
            return
        depth+=1

        self.seen.append(url)
        for skip in self.blacklist:
            if url.endswith(skip):
                return
        print(f"Fetching file listing: {url}")
        reqs = requests.get(url)
        base = url
        soup = BeautifulSoup(reqs.text, 'html.parser')
        urls = []
        for link in soup.find_all('a'):
            url = link.get('href')
            if url is None:
                continue
            url = self.absolute_url(base, url)
            filename = os.path.basename(url)
            fmt = parse.parse(self.pattern, filename)
            if fmt is not None:
                self.add(url, fmt)
            elif url.find("..") == -1 and self.recursive and url.startswith(baseurl) and len(url) >= len(baseurl):
                avoid = False
                if "avoid_paths" in self.params:
                    for p in self.params["avoid_paths"]:
                        if url.find(p) >= 0:
                            avoid = True
                            break

                if not avoid:        
                    self.lurk(baseurl, url, depth=depth)


        
        if depth > 1 or self.params["constraints"]["version"] != "latest": 
            return
        
        # Now, we need to filter out only latest version of iso files
        # I know, that this logic sucks donkey's ass, but I can't spare 
        # a moment to rewrite it properly. 

        def determine(self, a):
            filename = os.path.basename(a)
            fmt = parse.parse(self.pattern, filename)
            need = 0

            if "version" in fmt:
                need += 1

            if "date" in fmt:
                need += 1

            got = 0

            if hasattr(self, "maxversion") and "version" in fmt and fmt["version"] == self.maxversion:
                got += 1

            version = fmt["version"]
            if version in self.maxdate and "date" in fmt:
                mdate = datetime.strptime(fmt["date"], self.date_format);
                if mdate >= self.maxdate[version]:
                    got += 1

            return (got == need)

        self.artifacts = set(self.artifacts)
        self.artifacts = [x for x in self.artifacts if determine(self, x)]

    def loot(self):
        for artifact in self.artifacts:
            print(f"Looting: {artifact}")
            #TODO: Use native python tools here? Catch sigint?
            filename = os.path.basename(artifact)
            os.system(f"wget -4 -c {artifact} -O {filename}")
            time.sleep(2)

class LootGoblin():
    def __init__(self, config):
        self.config = config
        self.targets = {}
        for c,v in config.items():
            tr = ISOTreasury(v)
            if "dateformat" in v:
                tr.set_date_format(v["dateformat"])
            tr.lurk()
            self.targets[c] = tr
        print("    ")

    def print(self):
        for name,target in self.targets.items():
            print(f"Config section '{name}'")
            for c in target.artifacts:
                print(f"  {c}")

    def loot(self, outdir):
        cwd = os.getcwd()
        os.chdir(outdir)
        for name,target in self.targets.items():
            target.loot()
        os.chdir(cwd)
        
parser = argparse.ArgumentParser()
parser.add_argument("--config", type=argparse.FileType('r'), required=True, help="Specify config file")
parser.add_argument("--test", action="store_true", default=False, help="Just print urls to download, but don't download anything")
parser.add_argument("--destination", default="./", help="Specify output directory")

args = parser.parse_args()

config = yaml.safe_load(args.config)
goblin = LootGoblin(config)

goblin.print()
if not args.test:
    goblin.loot(args.destination)

#for u in urls:
#    t = ISOTreasury(u, False)
#    t.lurk()
#    t.loot()
