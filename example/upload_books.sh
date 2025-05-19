#!/usr/bin/env bash

if [ ! -n "$1" ]
then
  echo "Upload processed book jpg files to the IIIF server"
  echo "Usage: $0 file.csv"
  exit $E_BADARGS
fi

#load the CFG_IIIF_DATA_PATH and CFG_DIGILIB_PATH environment variables
source .env 

workdir=$CFG_DIGILIB_PATH  #data/digilib

function upload_jpg_files () {
  while IFS=';' read -ra array; do
    DirName=("${array[0]}")
    SourcePath=("${array[2]}")
    Title=("${array[3]}")
    Author=("${array[4]}")
    Language=("${array[5]}")
    Year=("${array[6]}")
    Publisher=("${array[7]}")
    if [[ "$Title" == "Title" ]]; then
      continue
    fi
  
    (
    echo Uploading  $workdir/$DirName
    cd $workdir/$DirName
    scp -r "$DirName" $CFG_IIIF_DATA_PATH
    )
  done < $1
}

upload_jpg_files $1
