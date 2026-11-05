"""Small observed action records; never copy prompts, commands or tool output."""
from pathlib import PureWindowsPath


def label(tool,arguments=None):
    name=str(tool).lower()
    if any(word in name for word in ('read','get-content','glob','grep','search','fetch','browse')):text='Oxuma və axtarış'
    elif any(word in name for word in ('edit','write','patch','filechange')):text='Fayl dəyişikliyi'
    elif any(word in name for word in ('test','unittest','pytest')):text='Test əməliyyatı'
    elif any(word in name for word in ('task','todo','plan')):text='Plan yenilənməsi'
    elif any(word in name for word in ('exec','bash','powershell','command')):text='Əmr əməliyyatı'
    else:text='Alət əməliyyatı'
    if isinstance(arguments,dict):
        path=arguments.get('file_path') or arguments.get('path')
        if isinstance(path,str) and len(path)<2000:
            name=PureWindowsPath(path).name
            if name and len(name)<120:text+=' · '+name
    return text


def append(records,identity,text,status='completed',limit=8):
    records=[row for row in records if isinstance(row,dict)] if isinstance(records,list) else []
    if not identity or any(row.get('id')==identity for row in records):return records
    sequence=int(records[-1].get('sequence',0))+1 if records else 1
    return (records+[dict(id=str(identity)[:160],step=str(text)[:300],status=status,sequence=sequence)])[-limit:]
