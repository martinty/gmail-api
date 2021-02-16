#!/bin/bash

SCRIPTPATH="$( cd "$(dirname "$0")" ; pwd)"

cd $SCRIPTPATH

rm -f feedback.txt
rm -rf ../automated-testing/src_zip
mkdir ../automated-testing/src_zip

cp handin.zip ../automated-testing/src_zip

cd ../automated-testing
./setup.sh run release
cp build/feedback.txt $SCRIPTPATH
cd $SCRIPTPATH

