#!/bin/bash -x

# Description: Use the current project's README.md file to publish all local IP addresses

# Global variable definition
LOGDIR="../log"
LOGFILE="push_my_ip.log"
USER=ferree

# Init logger helper function
init_log () {
  rm -rf $LOGDIR
  mkdir $LOGDIR
}

# Logger helper function
log () {
  echo $(date) : "$1" >> $LOGDIR/$LOGFILE
}

# Waits for system time synchronization, then returns date/time
get_time () {
  until [[ "$(timedatectl status)" == *"System clock synchronized: yes"* ]]; do
    log "waiting for time sync 5s"
    sleep 5
  done
  echo -e "$(date)"
}

# Returns all local IPv4 interface with their address
get_my_ips () {
  log "start get_my_ips"

  # Check the inferfaces
  ret=$(ip -o -4 addr | grep -v "lo " | awk -F/ '{print $1}' | awk -v user=$USER '{print "- "$2" : "$4" [SSH](ssh://"user"@"$4") [SFTP](sftp://"user"@"$4")"}')
  if [[ "$ret" == *"wlan0"* ]] ; then
    sig_strength=$(iwconfig wlan0 | grep Quality | awk -F"[=/]" '{print $2}')
    ret="${ret} - Signal strength: $((100 * ${sig_strength} / 70))%"
  fi
  # If eth0 is found but not wlan0, wait for WLAN0 for 30s
  if [[ "$ret" == *"eth0"* ]] && [[ "$ret" != *"wlan0"* ]] ; then
    for i in {1..10} ; do
      ret=$(ip -o -4 addr | grep -v "lo " | awk -F/ '{print $1}' | awk -v user=$USER '{print "- "$2" : "$4" [SSH](ssh://"user"@"$4") [SFTP](sftp://"user"@"$4")"}')
      if [[ "$ret" == *"wlan0"* ]] ; then
        sig_strength=$(iwconfig wlan0 | grep Quality | awk -F"[=/]" '{print $2}')
        ret="${ret} - Signal strength: $((100 * ${sig_strength} / 70))%"
        break
      fi
      sleep 3
    done
  fi

  log "IP found:"
  log "$ret"
  echo -e "$ret"
}

# Main:
#======

pushd $(dirname $0) >/dev/null 2>&1  # change to current file directory
init_log                             # initialize log
timestamp=$(get_time)                # initialize system time
log "start main with timestamp: $timestamp"

git status | grep corrupt
ret=`echo $?`
if [[ "$ret" == "0" ]] ; then
    find .git/objects/ -size 0 -delete
    log "recover from corrupt .git"
fi
git pull

# Overwrite README.md file
cat >../README.md <<EOL
# my-rpi

As of $timestamp, my Raspberry-Pi has the following IP:

$(get_my_ips)
EOL
# End of file output
log "committing to git repo"
git commit -am "auto IP commit $timestamp" >/dev/null 2>&1 # commit the change in git
git push origin master                     >/dev/null 2>&1 # push to GitLab
log "done"
popd >/dev/null 2>&1                                       # return to original folder
