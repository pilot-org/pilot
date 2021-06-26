from loguru import logger

NOTIFICATION = 'NOTIFICATION'
CONNECTION='CONNECTION'
CMD_READ='CMD_READ'
CMD='CMD'

connect_level = logger.level(CONNECTION, no=22, color='<light-cyan>')
cmd_read_level = logger.level(CMD_READ, no=23, color='<fg #AA6939>')
cmd_level = logger.level(CMD, no=27, color='<light-magenta>')
notification_level = logger.level(NOTIFICATION, no=29, color='<yellow>')
