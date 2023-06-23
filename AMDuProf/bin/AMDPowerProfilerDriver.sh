#! /bin/bash

IS_DISTRO_RHEL=0
IS_DISTRO_SUSE=0
IS_DISTRO_UBUNTU=0

check_exe_permission() {
    # script can be executed only with root permission.
    if [ "$(id -u)" != "0" ]; then
        echo "Please execute this script with root permission."
        exit 0
    fi
}

module_in_use() {
    # check if proc entry exists for state
    if [ -f /proc/AMDPowerProfiler/state ] 
    then
        # if state is set then module is in use
        MOD_IN_USE=`cat /proc/AMDPowerProfiler/state`
        if [ $MOD_IN_USE -eq "1" ]
        then
            echo "Unable to $1 AMD Power Profiler, module is in use."
            echo "cat /proc/AMDPowerProfiler/state will show status of the module, 1 if module is in use."
            echo "Please run the AMDPowerProfilerDriver.sh script to $1, when the power profiler is not in use."
            exit 0
        fi
    fi

    # compatiblity with prior versions, as /proc/AMDPowerProfiler/state file does not exist
    count=`lsmod | grep -e amdtPwrProf -e pcore  -e AMDPowerProfiler | awk '{print $NF}'`
    if [ -n "$count" ]
    then 
        if [ "$count" -ne "0" ]
        then
            echo "Unable to $1 AMD Power Profiler, module is in use."
            echo "Please run the AMDPowerProfilerDriver.sh script to $1, when the power profiler is not in use."
            exit 0
        fi
    fi
}

set_module_name () {
    # Module name.
    MODULE_NAME=$1
}

set_version_name() {
    # Module version.
    MODULE_VERSION=$(cat AMDPowerProfilerVersion)
}

set_src_path() {
    # Source path.
    MODULE_SOURCE_PATH=/usr/src/$MODULE_NAME-$MODULE_VERSION
}

check_distro() {
    count=`cat /etc/os-release | grep -we NAME -we PRETTY_NAME -we ID_LIKE | grep -i suse | wc -l`
    if [[ -f /etc/SuSE-release || $count -gt 0 ]];
    then
      IS_DISTRO_SUSE=1
    elif [ -f /etc/redhat-release ]; then
      IS_DISTRO_RHEL=1
    else
      IS_DISTRO_UBUNTU=1
    fi
}

prompt_if_suse_unsupported () {
    # for SuSE, allow_unsupported_modules flag should be set,
    # to install 3rd Party driver/module. 
    if [ $IS_DISTRO_SUSE -eq 1 ]; then
      UNSUPPORTED_DEV_CONF_FILE=`ls /etc/modprobe.d | grep unsupported-modules`
      if [ -f /etc/modprobe.d/${UNSUPPORTED_DEV_CONF_FILE} ]; then
        count=`cat /etc/modprobe.d/${UNSUPPORTED_DEV_CONF_FILE} | grep "^allow_unsupported_modules 0" | wc -l`
        # if allow_unsupported_modules == 0, set it to 1.
        if [ $count -gt 0 ]
        then
            echo 'Cannot install AMD Power Profiler.'
            echo "Use --allow-unsupported or set allow_unsupported_modules to 1 in /etc/modprobe.d/${UNSUPPORTED_DEV_CONF_FILE} for installation."
            exit 0
        fi
      else
          echo 'Cannot install AMD Power Profiler.'
          echo "Module configuration file /etc/modprobe.d/${UNSUPPORTED_DEV_CONF_FILE} not found."
          exit 0
      fi     
    fi
}

add_src () {
    # untar the file and install it in /usr/src/...
    tar -zxf AMDPowerProfilerDriverSource.tar.gz -C /usr/src/ 
}

install_dkms () {
    # DKMS is installed.
    MODULE_SOURCE=`pwd`

    cd $MODULE_SOURCE_PATH 

    # uninstall dkms module for pcore
    make cleandkms
    if [ $? -ne 0 ] ; then
        echo "ERROR: AMD Power Profiler driver installation failed while uninstalling the previously installed driver." 
        exit 0
    fi

    # install dkms module for pcore
    make dkms
    if [ $? -ne 0 ] ; then
        echo "ERROR: AMD Power Profiler driver installation failed." 
        exit 0
    fi

    cd $MODULE_SOURCE 
}

install_non_dkms () {
    # DKMS not installed 
    cd $MODULE_SOURCE_PATH 

    # cleanup
    make clean
    if [ $? -ne 0 ] ; then
        echo "ERROR: AMD Power Profiler driver build failed while uninstalling the previously installed driver." 
        exit 0
    fi

    make 
    if [ $? -ne 0 ] ; then
        echo "ERROR: AMD Power Profiler driver build failed." 
        exit 0
    fi

    make install
    if [ $? -ne 0 ] ; then
        echo "ERROR: AMD Power Profiler driver installation failed." 
        exit 0
    fi

    cd -
}

install_mod() {
    DKMS=`which dkms 2>/dev/null`
    if [ -n "$DKMS" ]
    then
        install_dkms
    else
        install_non_dkms
    fi
}

create_proc_entry () {
    #check if module is loaded 
    if [ -f /proc/${MODULE_NAME}/device ] 
    then
        #Module loaded, Create the device file
        VER=`cat /proc/${MODULE_NAME}/device`
        if [[ ! -a /dev/${MODULE_NAME} ]]
        then
            mknod /dev/${MODULE_NAME} -m 666 c $VER 0
            if [ $? -ne 0 ] ; then
                echo "ERROR: AMD Power Profiler driver installation failed while creating device file." 
                exit 0
            fi
        fi
    else
        echo "ERROR: AMD Power Profiler driver installation failed while loading driver." 
        exit 0
    fi
}

add_rhel_module_entry() {
  # RHEL/CENTOS system 
  # 1. Add the modprobe command to /etc/rc.modules
  if [ ! -f /etc/rc.modules ]
  then
      touch /etc/rc.modules
  fi

  count=`grep ${MODULE_NAME} /etc/rc.modules | wc -l`
  if [ ! $count -gt 0 ]
  then
      echo modprobe ${MODULE_NAME} >> /etc/rc.modules
      chmod +x /etc/rc.modules
  fi

  # commands to be executed from init on system startup
  if [ ! -f /etc/rc.local ]
  then 
      touch /etc/rc.local
  fi

  if [ -f /etc/rc.local ]
  then
      count=`grep ${MODULE_NAME} /etc/rc.local | wc -l`
      if [ ! $count -gt 0 ]
      then
          # Add a command in the rc.local file to create the device file on reboot
          echo mknod /dev/${MODULE_NAME} -m 666 c \`cat /proc/${MODULE_NAME}/device\` 0 >> /etc/rc.local

          if [ ! -x /etc/rc.local ]
          then
              chmod +x /etc/rc.local
          fi

          # if file is not executable, make it 
          if [ ! -x /etc/rc.d/rc.local ]
          then
              chmod +x /etc/rc.d/rc.local
          fi
      fi
  fi
}

add_suse_module_entry() {
  UNSUPPORTED_DEV_CONF_FILE=`ls /etc/modprobe.d | grep unsupported-modules`
  if [ -f /etc/modprobe.d/${UNSUPPORTED_DEV_CONF_FILE} ]; then
    if [ -f /etc/modprobe.d/unsupported-modules ]; then
      # for SuSE, 
      # modules to be loaded once the main filesystem is active
      if [ -f /etc/sysconfig/kernel ]
      then
          count=`grep ${MODULE_NAME} /etc/sysconfig/kernel | wc -l`
          if [ ! $count -gt 0 ]
          then
              sed -i "s/.*MODULES_LOADED_ON_BOOT.*/&\nMODULES_LOADED_ON_BOOT=\"${MODULE_NAME}\"/" /etc/sysconfig/kernel
          fi
      fi

      # commands to be executed from init on system startup
      if [ -f /etc/rc.d/boot.local ]
      then 
          count=`grep ${MODULE_NAME} /etc/rc.d/boot.local | wc -l`
          if [ ! $count -gt 0 ]
          then
              echo mknod /dev/${MODULE_NAME} -m 666 c \`cat /proc/${MODULE_NAME}/device\` 0 >> /etc/rc.d/boot.local 
          fi
      fi
    else
      count=`lsinitrd | grep ${MODULE_NAME} | wc -l `
      if [ ! $count -gt 0 ]
      then
          if [ ! -f /etc/modules-load.d/${MODULE_NAME}.conf ]
          then 
              touch /etc/modules-load.d/${MODULE_NAME}.conf
              echo ${MODULE_NAME} >> /etc/modules-load.d/${MODULE_NAME}.conf  
          fi

          INITRAMFS=/boot/initrd-`uname -r`
          dracut --add-drivers ${MODULE_NAME} ${INITRAMFS} --force -q 2> /dev/null
          dracut -f -q 2>/dev/null 
      fi

      # commands to be executed from init on system startup
      if [ ! -f /etc/init.d/boot.local ]
      then 
          touch /etc/init.d/boot.local
          echo "#! /bin/bash" >> /etc/init.d/boot.local
      fi

      if [ ! -x /etc/init.d/boot.local ]
      then
          chmod +x /etc/init.d/boot.local
      fi

      # commands to be executed from init on system startup
      if [ -f /etc/init.d/boot.local ]
      then 
          count=`grep ${MODULE_NAME} /etc/init.d/boot.local | wc -l`
          if [ ! $count -gt 0 ]
          then
              echo mknod /dev/${MODULE_NAME} -m 666 c \`cat /proc/${MODULE_NAME}/device\` 0 >> /etc/init.d/boot.local 
          fi
      fi
    fi
  fi
}

add_ubuntu_module_entry() {        
  if [ ! -f /etc/modules ]
  then
      touch /etc/modules
      chmod +x /etc/modules
  fi

  count=`grep ${MODULE_NAME} /etc/modules | wc -l`
  if [ ! $count -gt 0 ]
  then
      echo ${MODULE_NAME} >> /etc/modules
  fi

  # commands to be executed from init on system startup
  if [ ! -f /etc/rc.local ]
  then 
      touch /etc/rc.local
  fi

  count=`grep ${MODULE_NAME} /etc/rc.local | wc -l`
  if [ ! $count -gt 0 ]
  then
      # in Ubuntu  distribution 16.04 onwards /etc/rc.local
      # is not executed at boot up. Following changes are required
      ubuntuVer=$(echo $(lsb_release -sr) | awk -F'.' '{print $1}')
      if [ $ubuntuVer -ge 16 ]
      then
          chmod +x /etc/rc.local
          sed -i '/bash/d' /etc/rc.local
          echo "#!/bin/bash" >> /etc/rc.local
      fi
      
      sed -i '/exit 0/d' /etc/rc.local
      echo mknod /dev/${MODULE_NAME} -m 666 c \`cat /proc/${MODULE_NAME}/device\` 0 >> /etc/rc.local
      echo exit 0 >> /etc/rc.local 
  fi
}

add_module_entry () {
    # Make the module to be loaded on reboot
    if [ $IS_DISTRO_RHEL -eq 1 ]
    then
      add_rhel_module_entry
    elif [ $IS_DISTRO_SUSE -eq 1 ]
    then
      add_suse_module_entry
    elif [ $IS_DISTRO_UBUNTU -eq 1 ]
    then
        # Ubuntu OS
        # modules to be loaded once the main filesystem is active
        add_ubuntu_module_entry
    fi
}

uninstall_dkms() {
    # DKMS is installed
    MODULE_SOURCE=`pwd`
    if [[ -d $MODULE_SOURCE_PATH ]]; then
        cd $MODULE_SOURCE_PATH 

        # uninstall dkms entry 
        make cleandkms
        if [ $? -ne 0 ] ; then
            echo "ERROR: Uninstalling the AMD Power Profiler driver failed." 
            exit 0
        fi
        cd $MODULE_SOURCE 
    else
        rmmod ${MODULE_NAME}
    fi
}

uninstall_module() {
    # remove module.
    KO="/lib/modules/`uname -r`/kernel/drivers/extra/${MODULE_NAME}.ko"
    if [ -f ${KO} ]
    then
        rm  -f ${KO}
    fi

    # remove module from dkms path 
    DKMS_KO="/lib/modules/`uname -r`/updates/dkms/${MODULE_NAME}.ko"
    if [ -f ${DKMS_KO} ]
    then
        rm  -f ${DKMS_KO}
    fi

    DEV="/dev/${MODULE_NAME}"
    count=`ls /dev | grep ${MODULE_NAME} | wc -l`
    if [ $count -gt 0 ]
    then
        rm  -f ${DEV}
    fi

    #load the existing kernel module if exists.
    count=`lsmod | grep ${MODULE_NAME} | wc -l`
    # if module installed.
    if [ $count -gt 0 ]
    then 
        DKMS=`which dkms 2>/dev/null`
        if [ -n "$DKMS" ]
        then
            uninstall_dkms
        else
            rmmod ${MODULE_NAME} 
        fi
    fi
}

delete_redhat_module_entry() {
  if [ -f /etc/rc.local ]
  then
      count=`grep ${MODULE_NAME} /etc/rc.local | wc -l`
      if [ $count -gt 0 ]
      then
          sed -i "/${MODULE_NAME}/d" /etc/rc.local
      fi
  fi

  # RHEL/CENTOS system 
  # remove the modprobe command to /etc/rc.modules
  if [ -f /etc/rc.modules ]
  then
      count=`grep ${MODULE_NAME} /etc/rc.modules | wc -l`
      if [ $count -gt 0 ]
      then
          sed -i "/${MODULE_NAME}/d" /etc/rc.modules
      fi
  fi
}

delete_ubuntu_module_entry() {
  if [ -f /etc/rc.local ]
  then
      count=`grep ${MODULE_NAME} /etc/rc.local | wc -l`
      if [ $count -gt 0 ]
      then
          sed -i "/${MODULE_NAME}/d" /etc/rc.local
      fi
  fi

  # Ubuntu OS
  if [ -f /etc/modules ]
  then
      count=`grep ${MODULE_NAME} /etc/modules | wc -l`
      if [ $count -gt 0 ]
      then
          sed -i "/${MODULE_NAME}/d" /etc/modules
      fi
  fi
}

delete_suse_module_entry() {
  UNSUPPORTED_DEV_CONF_FILE=`ls /etc/modprobe.d | grep unsupported-modules`
  if [ -f /etc/modprobe.d/${UNSUPPORTED_DEV_CONF_FILE} ]; then
    if [ -f /etc/modprobe.d/unsupported-modules ]; then
      # SuSE system
      # remove modules from /etc/sysconfig/kernel
      if [ -f /etc/sysconfig/kernel ]
      then  
          mod_found=`grep ${MODULE_NAME} /etc/sysconfig/kernel | wc -l`
          # module found
          if [ $mod_found -gt 0 ]
          then
              sed -i "/MODULES_LOADED_ON_BOOT=\"${MODULE_NAME}\"/d" /etc/sysconfig/kernel
          fi
      fi

      if [ -f /etc/rc.d/boot.local ]
      then
          # remove the modprobe command from /etc/rc.d/boot.local
          mod_found=`grep ${MODULE_NAME} /etc/rc.d/boot.local | wc -l`
          if [ $mod_found -gt 0 ]
          then
              sed -i "/${MODULE_NAME}/d" /etc/rc.d/boot.local
          fi
      fi
    else
      # for SuSE 13.1 onwards 
      # modules to be loaded once the main filesystem is active
      count=`lsinitrd | grep ${MODULE_NAME} | wc -l `
      if [ $count -gt 0 ]
      then
        if [ -f /etc/modules-load.d/${MODULE_NAME}.conf ]
        then 
            rm -rf /etc/modules-load.d/${MODULE_NAME}.conf  
        fi

        INITRAMFS=/boot/initrd-`uname -r`
        dracut --omit-drivers ${MODULE_NAME} ${INITRAMFS} --force -q 2>/dev/null 
        dracut -f -q 2>/dev/null 
      fi

      if [ -f /etc/init.d/boot.local ]
      then
        # remove the modprobe command from /etc/init.d/boot.local
        mod_found=`grep ${MODULE_NAME} /etc/init.d/boot.local | wc -l`
        if [ $mod_found -gt 0 ]
        then
            sed -i "/${MODULE_NAME}/d" /etc/init.d/boot.local
        fi
      fi
    fi
  fi
}

delete_mod_entry() {
    if [ $IS_DISTRO_RHEL -eq 1 ]
    then
      delete_redhat_module_entry
    elif [ $IS_DISTRO_SUSE -eq 1 ]
    then
      delete_suse_module_entry
    elif [ $IS_DISTRO_UBUNTU -eq 1 ]
    then
      delete_ubuntu_module_entry
    fi
}

delete_src() {
    # delete the PP module source folder
    rm -rf /usr/src/${MODULE_NAME}-*  &> /dev/null

    # in case of DKMS non existence module entried 
    # must be cleared from dkms source tree
    DKMS=`which dkms 2>/dev/null`
    if [ -n "$DKMS" ]
    then
        rm -rf sudo rm -rvf /var/lib/dkms/${MODULE_NAME}  &> /dev/null
    fi
}

common_uninstaller() {
    set_version_name
    set_src_path
    uninstall_module
    delete_mod_entry
    delete_src
}

uninstall_pcore() {
    set_module_name pcore
    common_uninstaller
}

uninstall_amdtPwrProf() {
    set_module_name amdtPwrProf 
    common_uninstaller
}

uninstall_AMDPowerProfiler() {
    set_module_name AMDPowerProfiler 
    common_uninstaller
}

uninstall() {
    # earlier Power Profiler driver named pcore and amdtPwrProf
    # uninstall if old module exists
    uninstall_pcore
    uninstall_amdtPwrProf

    # uninstall power profiler current module
    uninstall_AMDPowerProfiler
}

install() {
    # set module name
    set_module_name AMDPowerProfiler 
    # set driver version number
    set_version_name
    # set driver sorce file path 
    set_src_path
    # prompt for SuSE version
    prompt_if_suse_unsupported
    # add source file in the source folder
    add_src
    # install module
    install_mod
    # create mknod entry
    create_proc_entry
    # add module entry, required after system reboot
    add_module_entry
}

verify_kernel_header() {
    # kernel headers is linked to build directory
    HEADER_SRC="/lib/modules/`uname -r`/build"

    if [ $IS_DISTRO_RHEL -eq 1 ];
    then
      CMD="sudo yum install kernel-devel-$(uname -r)"
    elif [ $IS_DISTRO_SUSE -eq 1 ];
    then
      KERN_VER=$(uname -r) # get the kernel version
      KERN_VER=${KERN_VER%-*} #remove everything after last -
      KERN_HEADER=$(zypper se -s Kernel-default-devel |grep ${KERN_VER} 2>/dev/null) #get kernel header
      KERN_HEADER=$(echo "$KERN_HEADER" | grep -o "$KERN_VER.*" | awk '{print $1;}')
      if [ ! -z "$KERN_HEADER" ];then
         CMD="sudo zypper install kernel-default-devel-${KERN_HEADER}"
      else
         CMD="sudo zypper install kernel-default-devel"
      fi
    elif [ $IS_DISTRO_UBUNTU -eq 1 ];
    then
      CMD="sudo apt-get install linux-headers-$(uname -r)"
    fi
    
    if [ ! -d ${HEADER_SRC} ]
    then
        echo "ERROR: Linux headers is required for installing AMD Power Profiler driver."
        echo "       Please install the sources using"
        tput bold    # put the text in bold
        echo         ${CMD}
        tput sgr0    #Reset text attributes to normal without clear.
        echo "       and then start the installation again."
        exit 0
    fi
}

installer() {
    # verify if the linux-header source exists
    verify_kernel_header 
 
    # uninstall all the previous version installed
    uninstall

    # install the latest driver
    echo "Installing AMD Power Profiler driver."
    install
    echo "AMD Power Profiler driver installation completed successfully."
}

un_installer() {
    # uninstall all the previous version installed
    echo "Uninstalling the AMD Power Profiler driver."
    uninstall
    echo "AMD Power Profiler driver uninstallation completed successfully."
}

usage()  {
    echo "Usage:"
    echo "Install AMD Power Profiler:    sudo ./AMDPowerProfilerDriver.sh install"
    echo "Uninstall AMD Power Profiler:  sudo ./AMDPowerProfilerDriver.sh uninstall"
}

# check the distrobution type
# presently implemented for SuSE, can be extended to other distro also
check_distro

# check for root permission
check_exe_permission

# check if module in use
module_in_use $1

# number of arguments can not be greater then 2
if [ "$#" -ne 1 ] ; then
    echo "Invalid number of arguments"
    echo ""
    usage 
    exit 0
fi 

case $1 in
    install)
        # install driver
        installer
    ;;

    uninstall)
        # un install driver
        un_installer
    ;;

    *)
        # in appropiate input
        usage 
    ;;
esac 
