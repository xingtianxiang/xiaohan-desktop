"""Use the existing Git credential helper for the authorized Mac build repository."""
import os
import subprocess
import sys


def main():
    env=os.environ.copy();env['GIT_TERMINAL_PROMPT']='0';env['GCM_INTERACTIVE']='never'
    auth=subprocess.run(['git','credential','fill'],input='protocol=https\nhost=github.com\nusername=xingtianxiang\n\n',text=True,capture_output=True,env=env)
    if auth.returncode:
        raise SystemExit('No usable Git credential; interactive GitHub login is required.')
    fields=dict(line.split('=',1) for line in auth.stdout.splitlines() if '=' in line)
    if not fields.get('password'):raise SystemExit('Git credential helper did not provide authentication.')
    env['GH_TOKEN']=fields['password']
    account=subprocess.run(['gh','api','user','--jq','.login'],env=env,text=True,capture_output=True)
    if account.returncode or account.stdout.strip()!='xingtianxiang':
        raise SystemExit('Git credential did not authenticate the authorized account.')
    result=subprocess.run(['gh',*sys.argv[1:]],env=env)
    raise SystemExit(result.returncode)


if __name__=='__main__':main()
