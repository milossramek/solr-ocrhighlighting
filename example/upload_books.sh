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
#DRY_RUN=--dry-run

function upload_jpg_files () {
  #upload the csv file
  rsync $DRY_RUN -av  $1 $CFG_DATA_REMOTE_PATH/
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
    echo Uploading  $workdir/$DirName to $CFG_IIIF_DATA_PATH
    cd $workdir/$DirName
    #rsync -rtv --exclude="*orig.jpg" ZDejVedTechSlov_I omekal:/var/www/iiif
    #rsync -rtv --exclude="*orig.jpg" $DirName $CFG_IIIF_DATA_PATH
    rsync $DRY_RUN -rtv --exclude="*orig.jpg" $DirName $CFG_IIIF_DATA_PATH
    )
    #upload xml files and pages.json
    echo "rsync $DRY_RUN -av --exclude '*/' --exclude '*orig.xml' $workdir/$DirName/ $CFG_DATA_REMOTE_PATH/$DirName/"
    rsync $DRY_RUN -av --exclude '*/' --exclude '*orig.xml' $workdir/$DirName/ $CFG_DATA_REMOTE_PATH/$DirName/
  done < $1
}

upload_jpg_files $1
