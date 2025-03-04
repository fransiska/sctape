import glob
import sys
import os
import jsonparse
import audioparse
import bitparse
import basparse
import wavparse
import tzxparse
import basicparse
from section import parseBytesSections,printSummary,listContent,getSections
from  util import removeExtension,rhoSweep
import getopt
from pathlib import Path
import hashlib
import json
import traceback

version="0.01"


def audioToRemasteredBit(filename,levell,levelh,opts): #levels are referred to max value, lperiod in seconds
    d=audioparse.getRawSection(filename,levell,levelh,opts)
    if "pitch" in opts:
        pitch=float(opts["pitch"])
    else:
        pitch=1
    d=getSections(d,pitch)
    if len([s for s in d["sections"] if s["type"]=="bytes"])<2:
        raise Exception("nothing to parse")

    parseBytesSections(d["sections"],True)
    return d


def audioRead(filename,opts):
    if "level" in opts:
        lev=float(opts["level"])
        d=audioparse.getRawSection(filename,lev,lev,opts)                   
        return d
    else:    
        return rhoSweep(audioToRemasteredBit,filename,"auto",opts)


# def wavRemaster(filename,d):
#     bs=bitparse.toBitRemaster(d)
#     filename="R_"+removeExtension(filename)+".wav"
#     wavparse.writeWav(filename,bs)

# def tzxRemaster(filename,d):
#     bs=bitparse.toBitRemaster(d)
#     filename="R_"+removeExtension(filename)+".tzx"
#     tzxparse.writeTzxFromBs(filename,bs)


def printInfo(filename,d):
    print("INFO",json.dumps(d["info"],sort_keys=True, indent=4))
    
readers={
    "mp3":audioRead,
    "wav":audioRead,
    "bit":bitparse.getSections,
    "json":jsonparse.jsonDeserialize,
    "tzx":tzxparse.readTzx,
    "bas":basparse.readBas,
    "basic":basicparse.readBasic
}

writers={
    "json":jsonparse.writeJson,
    "bit":lambda f,d: bitparse.writeBit(f,d,True),
    "rawbit":lambda f,d: bitparse.writeBit(f,d,False),
    "bas":basparse.writeBas,
    "wav":wavparse.writeWav,
    "list":lambda f,d: print(f,listContent(d)),
    "summary":lambda f,d: None,
    "tzx":tzxparse.writeTzx,
    "basic":basicparse.writeBasic,
    "bin":basparse.writeBin,
    "info":printInfo
}

remrate=44100



def getMd5(filename):
    md5_hash = hashlib.md5()
    md5_hash.update(open(filename, "rb").read())
    return md5_hash.hexdigest()




def addSuffix(filename,suff):
    tok=filename.split(".")
    return ".".join(tok[:-1])+suff+"."+tok[-1]


def getOutname(filename,outputtype,opts):
    suffix={"none":"","signal":"","bit":"_rb","section":"_rs"}
    
    suff=suffix[opts["remaster"]]
    if "output_filename" in opts:
        outPath=Path(opts["output_filename"])
    else:        
        outPath=Path(removeExtension(filename)+suff+"."+outputtype)
    if "output_dir" in opts:
        outPath=Path(opts["output_dir"]).joinpath(outPath)
    return outPath

def convert(filename,outputtype,opts):
    if outputtype not in writers:
        print("Unknow output type",outputtype)
        print("Known types are",writers.keys())
        raise Exception("Unknown output type ")

    print("specified options",opts)
    if "input_type" in opts:
        inputtype=opts["input_type"]
    else:
        inputtype=filename.split(".")[-1]

    
    if "remaster" not in opts or opts["remaster"]=="auto":
        if inputtype in ["basic","bas"]:
            remaster="section"
        elif inputtype in ["bit"]:
            remaster="bit"
        else:
            remaster="signal"
    else:
         remaster=opts["remaster"]
         remlevels=["none","auto","signal","bit","section"]
         if remaster not in remlevels:
             errmessage="Unknown remaster level "+remaster+"options are "+" ".join(remlevels)
             raise Exception(errmessage)        

    opts["remaster"]=remaster
    outfile=getOutname(filename,outputtype,opts)    
    if "no_overwrite" in opts and os.path.isfile(outfile):
        print(str(outfile)+" already exists.")
        return

    


    

    print("Reading input")
    d=readers[inputtype](filename,opts)


    
    info=d.setdefault("info",{})


    info.setdefault("source",{
        "filename":Path(filename).name,
        "md5":getMd5(filename)
    })    
    tool=info.setdefault("tool",{})
    tool["name"]="tapeconv"           
    tool["version"]=version
    tool["url"]="https://github.com/fabiodl/sctape"
    tool.setdefault("settings",{})["remaster"]=remaster
    
    print("Identifying bytes")
    if "pitch" in opts:
        pitch=float(opts["pitch"])
    else:
        pitch=1

    getSections(d,pitch)
    ignoreSectionErrors= "ignore_section_errors" in opts
    print("Identifying sections")
    parseBytesSections(d["sections"],not ignoreSectionErrors)
    if outputtype!="list":
        printSummary(d,False)


    if remaster=="section":
        print("Remastering sections")
        d["bitrate"]=remrate
        d["signal"]=bitparse.genSignal(d,remrate,True)
    elif remaster=="bit":
        print("Remastering bits")
        d["bitrate"]=remrate
        d["signal"]=bitparse.genSignal(d,remrate,False)
    print("Writing output",outfile)
    parent_dir = outfile.parent
    parent_dir.mkdir(parents=True, exist_ok=True)    
    writers[outputtype](str(outfile),d)    


if __name__=="__main__":
    options=["level=","pitch=","mode=","ignore_section_errors","remaster=","batch","no_overwrite","output_dir=","output_filename=","program_name=","input_type="]
    optlist,args=getopt.getopt(sys.argv[1:],"",options)
    if len(sys.argv)<2:
        print("Usage ",sys.argv[0]," inputfile outputtype")
        print("Available options",options)
    else:
        opts={k[2:]:v for k,v in optlist}

        if "batch" in opts:
            files=[f.strip() for f in open(args[0]).readlines()]
        else:            
            if os.path.isfile(args[0]):
                files=[args[0]]
            else:
                files=sorted(glob.glob(args[0]))

            if len(args)>=1 and len(files)==0:            
                print(f"No such input file[s]: '{args[0]}'",)
        ok=[]
        bad=[]
        for filename in files:
            try:
                print("converting",filename)
                print("target:",args[1])
                convert(filename,args[1],opts)
                ok.append(filename)
            except Exception as e:
                print("Impossible to convert",filename,":",
                ''.join(traceback.format_exception(None, e, e.__traceback__)))
                bad.append(filename)
            # raise
        if len(ok):
            print("Successfully converted ",ok)
        if len(bad):
            print("Failed converting ",bad)
