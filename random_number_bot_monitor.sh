#!/bin/bash
script_dir="/root/apps/random-number-bot/"
running_file="random_number_bot.running"

mail_sent_file="monitor_mail_sent.txt"

log_file="random_number_bot.log"

cd $script_dir

pid=`cat $running_file`

kill -0 $pid
kill_ret=$?

if [ "$kill_ret" -ne "0" ] && [ ! -f $mail_sent_file ]
then
    echo "mail sent" > $mail_sent_file
    (echo "random_number_bot LOG"; tail -40 $log_file;) | mail -t jjmerri88@gmail.com -s "Random Number Bot Not Running!"
fi

if [ "$kill_ret" -eq "0" ] && [ -f $mail_sent_file ]
then
    rm $mail_sent_file
fi

exit 0
