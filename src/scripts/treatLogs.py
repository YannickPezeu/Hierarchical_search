with open('logs.txt', "r", encoding='utf-8') as logs_file:
    logs = logs_file.read()
lines = logs.splitlines()

cleanedLines = []

for line in lines:
    if '| uvicorn.protocols.http.httptools' in line:
        continue
    else:
        cleanedLines.append(line)

with open('cleaned_logs.txt', "w", encoding='utf-8') as cleaned_logs_file:
    cleaned_logs_file.write('\n'.join(cleanedLines))