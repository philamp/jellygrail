#!/command/execlineb -P
sh -c "rar2fs -f -o allow_other,nonempty,auto_unmount,warmup=1 --seek-length=1 <src_folder> <dst_folder> > /jellygrail/log/<service_name> 2>&1"
