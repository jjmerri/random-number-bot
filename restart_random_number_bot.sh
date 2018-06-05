#!/bin/bash
script_dir="/root/apps/random-number-bot/"
logs_dir="logs/"
running_file="random_number_bot.running"

log_file="random_number_bot.log"

cd $script_dir


pid=`cat $running_file`

rm $running_file

kill -0 $pid
kill_ret=$?

while [ $kill_ret -eq 0 ]
do
    echo "PIDs $pid still running. Sleep for 60 secs"
    sleep 60

    kill -0 $pid
    kill_ret=$?
done

echo "renaming logs"
mv $log_file $logs_dir$log_file.$(date +%F-%T)

echo "PIDs stopped. Starting scripts."

python3 -u "random_number_bot.py" > $log_file 2>&1 &
pid=$!

echo "disowning $pid"
disown $pid

echo "complete"