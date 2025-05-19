#!/usr/bin/env bash
#set -o xtrace #be verbose

if [ ! -n "$1" ]
then
  echo "Process and ocr book pages"
  echo "Usage: $0 file.csv"
  exit $E_BADARGS
fi

source .env

workdir=$CFG_DIGILIB_PATH  #data/digilib
pages="../pages.json" #file to save dimensions of each page. Will be used to create the manifest for Mirador
                      #both the pages.json file and the xml files should be stored in the $workdir/$Dirname directory.
                      #However, processing happens in its subdirectory - therefore they have to be stored/copied to ist parent directory


#Check data correctness
function check_data_correctness () {
  errors=0
  while IFS=';' read -ra array; do
    DirName=("${array[0]}")
    Format=("${array[1]}")    #pdf or jpg allowed
    SourcePath=("${array[2]}")
    Title=("${array[3]}")
    Author=("${array[4]}")
    Language=("${array[5]}")
    Year=("${array[6]}")
    Publisher=("${array[7]}")
  
    #Ignore the header row
    if [[ "$Title" == "Title" ]]; then
      continue
    fi
  
    if [[ "$DirName" == "`basename $SourcePath`" ]]; then
        echo "Error in $1: DirName ($DirName, first column) is equal to directory name in SourcePath. Change it to something else."
        exit -1
    fi
  
    # Check Format validity
    allowed_files=("pdf" "jpg")
    found=false
    for value in "${allowed_files[@]}"; do
      if [[ "$Format" == "$value" ]]; then
        found=true
        break
      fi
    done
    if ! "$found"; then
        echo "Error at line $DirName: Invalid value '$Format' in the Format column (allowed values: pdf, jpg)."
        errors=1
    fi
  
    # Check language validity
    allowed_lang=("slk" "ces" "eng" "deu" "fra")
    found=false
    for value in "${allowed_lang[@]}"; do
      if [[ "$Language" == "$value" ]]; then
        found=true
        break
      fi
    done
    if ! "$found"; then
        echo "Error at line $DirName: Invalid value '$Language' in the Language column (allowed values: $allowed_lang)."
        errors=1
    fi
  
    # Check path correctness
    if [[ "$Format" == "pdf" ]]; then
      extension="${SourcePath##*.}"
      if [[ "$extension" != "pdf" ]]; then
          echo "Error at line $DirName: File '$SourcePath' does not have extension 'pdf'" 
          errors=1
      fi
      scp -r $SourcePath /tmp >/dev/null 
      if [ $? -ne 0 ]; then
          echo "Error at line $DirName: File '$SourcePath' does not exist (exit status: $?)"
          errors=1
      fi
    else    #director with jpg files
      rslt=$(scp $SourcePath /tmp 2>&1 >/dev/null)
      errmsg="No such file or directory"
      if echo "$rslt" | grep -q "$errmsg"; then
          echo "Error at line $DirName: $rslt"
          errors=1
      fi
    fi
done < $1

if [[ "$errors" == "1" ]]; then
    echo "Validity test of $1 finished. Fix the errors above."
    exit
else
    echo "Validity test of $1 finished."
    echo
fi
}

function convert_and_ocr_files () {
  while IFS=';' read -ra array; do
    DirName=("${array[0]}")
    Format=("${array[1]}")    #pdf or jpg allowed
    SourcePath=("${array[2]}")
    Title=("${array[3]}")
    Author=("${array[4]}")
    Language=("${array[5]}")
    Year=("${array[6]}")
    Publisher=("${array[7]}")
    if [[ "$Title" == "Title" ]]; then
      continue
    fi
  
    #Create work directory. iiif_prezi and solr will read data from there
    rm -rf $workdir/$DirName
    mkdir $workdir/$DirName
  
    if [[ "$Format" == "pdf" ]]; then
        page_data_dir=$workdir/$DirName/pages
        mkdir $page_data_dir  #directory to extract pdf pages to
        scp $SourcePath $page_data_dir
        echo Extracting pages from $Format file
        (
        cd $page_data_dir
        for pdf in *.pdf; do
          pdftoppm -r 300 $pdf page 2>/dev/null
          break    #There should be only one file, so break after the first one
        done
        )
    else
        scp -r $SourcePath $workdir/$DirName
        page_data_dir=$workdir/$DirName/`basename $SourcePath`
    fi
  
    #Convert files and build the pages.json file
    echo Processing $Title
    (
      cd $page_data_dir
      mkdir ../$DirName     #directory for the jpg files to be uploaded to the external iiif server
  
      shopt -s nullglob # Sets nullglob
      filelist=`ls *.{jpg,jpeg,png,ppm}`
      shopt -u nullglob # Unsets nullglob
  
      #count the files (necessary for json output)
      lastfilenum=0
      for element in $filelist; do
        ((lastfilenum++))
      done
      
      echo "{" > $pages
      echo "    \"title\": \"$Title\"," >> $pages
      echo "    \"pages\": [" >> $pages
      num=1
      for i in $filelist; do 
        pname=page_`printf "%04d" $num`
        echo $Title converting $i to $pname.jpg
        convert -contrast-stretch 1% -quality 80 $i $pname.jpg
        echo ocr of $pname.jpg to $pname.xml
        tesseract $pname.jpg $pname -l $Language alto 2>/dev/null
        sed -i -s "s/page_0/$pname/" $pname.xml
        width=`identify $pname.jpg|cut -d " " -f 3|cut -d x -f 1`
        height=`identify $pname.jpg|cut -d " " -f 3|cut -d x -f 2`
        if [[ "$num" == "$lastfilenum" ]]; then
          echo "        {\"page\":\"$num\",\"width\":\"$width\",\"height\":\"$height\"}" >> $pages
        else
          echo "        {\"page\":\"$num\",\"width\":\"$width\",\"height\":\"$height\"}," >> $pages
        fi
        mv $pname.jpg ../$DirName
        mv $pname.xml ..
        let "num = $(($num + 1))"
      done
      echo "    ]" >> $pages
      echo "}" >> $pages
  
      #Copy images to iiif server
      #cd ..
      #scp -r "$DirName" omekal:/var/www/iiif
    )
  done < $1
}

check_data_correctness $1
convert_and_ocr_files $1



