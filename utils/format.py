def format_size(bytes):
    if bytes == 0:
        return '0 B'
    sizes = ['B', 'KB', 'MB', 'GB', 'TB']
    i = 0
    while bytes >= 1024 and i < len(sizes) - 1:
        bytes /= 1024
        i += 1
    return f"{bytes:.2f} {sizes[i]}"

def format_time(seconds):
    if seconds < 60:
        return f"{seconds:.0f}s"
    if seconds < 3600:
        minutes = seconds // 60
        secs = seconds % 60
        return f"{minutes:.0f}m, {secs:.0f}s"
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    return f"{hours:.0f}h, {minutes:.0f}m"
