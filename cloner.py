from github import Github, GithubException
import argparse
from functools import partial
from threading import Thread
import concurrent.futures
from subprocess import Popen, PIPE
from shutil import rmtree
import os
import stat
from time import time
import inspect
from pathlib import Path

GITHUBAPITOKEN = os.getenv('GITHUBAPITOKEN')

def removepath(directory):
	directory = Path(directory)
	for item in directory.iterdir():
		if item.is_dir():
			try:
				os.chmod(item, stat.S_IWRITE)
				rmtree(item, ignore_errors=True)
				# os.rmdir(item)
			except Exception as e:
				pass
				#rmtree(item, ignore_errors=True)
		else:
			os.chmod(item, stat.S_IWRITE)
			item.unlink()
	directory.rmdir()

class Downloader(Thread):
	def __init__(self, url=None, destpath=None, debug=False, name=None, recursive=False, nodl=False):
		Thread.__init__(self)
		self.name = name
		self.recursive = recursive
		self.stdout = None
		self.stderr = None
		self.status = None
		self.url = url
		self.destpath = destpath
		self.debug = debug
		self.nodl = nodl
		if self.debug:
			print(f'[downloader] init stack {inspect.stack()[1][3]} {inspect.stack()[2][3]}')
	def run(self):
		if self.recursive:
			gitcmd = ['c:/apps/git/cmd/git.exe', 'clone', '--quiet --recursive', self.url, self.destpath]
		else:
			gitcmd = ['c:/apps/git/cmd/git.exe', 'clone', '--quiet', self.url, self.destpath]
		if self.debug:
			# print(f'[downloader] runstack {inspect.stack()[1][3]} {inspect.stack()[2][3]}')
			print(f'\t[gitcmd] {gitcmd}')
		if not self.nodl:
			if not os.path.exists(self.destpath):
				p = Popen(gitcmd, shell=False, stdout=PIPE, stderr=PIPE)
				self.status = p.wait()
				self.stdout, self.stderr = p.communicate()
				if self.debug:
					print(f'[downloader] status {self.status} stdout {self.stdout} stderr {self.stderr}')
			else:
				print(f'[downloader] {self.destpath} already exists, skipping')

def githubdownloader(destpath=None, debug=False, name=None, recursive=False, nodl=False, repo=None, url=None, overwrite=False):
	start_time = time()
	if repo is None:
		return -1
	if recursive:
		gitcmd = ['c:/apps/git/cmd/git.exe', 'clone', '--quiet', '--recursive', url, destpath]
	else:
		gitcmd = ['c:/apps/git/cmd/git.exe', 'clone', '--quiet', url, destpath]
	if not nodl:
		if not os.path.exists(destpath):
			print(f'[downloader] cloning {repo.name}')
			p = Popen(gitcmd, shell=False, stdout=PIPE, stderr=PIPE)
			status = p.wait()
			stdout, stderr = p.communicate()
			root_directory = Path(destpath)
			reposize = sum(f.stat().st_size for f in root_directory.glob('**/*') if f.is_file())
			if debug:
				print(f'[downloader] done {repo.name} status {status} stdout {stdout} stderr {stderr} time: {time()-start_time} size: {reposize}')
			return {'name':repo.name,'size':reposize, 'time': time()-start_time}
		elif os.path.exists(destpath) and overwrite:
			print(f'[downloader] {repo.name} {destpath} exists, overwriting {overwrite}')
			try:
				if os.path.exists(destpath):
					removepath(Path(destpath))
			except OSError as e:
				print(f'[downloader] error {e} {destpath}')
				return {'name':repo.name,'time': time()-start_time}
			else:
				p = Popen(gitcmd, shell=False, stdout=PIPE, stderr=PIPE)
				status = p.wait()
				stdout, stderr = p.communicate()
				return {'name':repo.name,'time': time()-start_time}
		elif os.path.exists(destpath):
			print(f'[downloader] {repo.name} {destpath} already exists, skipping')
			return {'name':repo.name,'time': time()-start_time}
		else:
			print(f'[downloader] {repo.name} {destpath}  skipping')
			return {'name':repo.name,'time': time()-start_time}
	else:
		print(f'[downloader] {repo.name} nodl set {destpath} not downloading')
		return {'name':repo.name,'time': time()-start_time}

def get_user_repos(git_username=None, gh=None, forks=False, debug=False):
	if debug:
		print(f'[getrepos] {inspect.stack()[1][3]} {inspect.stack()[2][3]}')
	g_user_sesssion = gh.get_user(git_username)
	g_repos = g_user_sesssion.get_repos()
	if forks:
		repos = [r for r in g_repos]
	else:
		repos = [r for r in g_repos if not r.fork]
	return repos


def main(args):
	starttime = time()
	if args.debug:
		print(f'[main] debug {args.debug}')
	github = Github(GITHUBAPITOKEN)
	repo_list = get_user_repos(args.user, gh=github, debug=args.debug)
	print(f'[{args.user}] {len(repo_list)} repos')
	threads = []
	totalsize = 0
	futures = []
	with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
		for repo in repo_list:
			dlpath = os.path.join(args.path, args.user, repo.name)
			func = partial(githubdownloader, url=repo.clone_url, destpath=dlpath, debug=args.debug, name=repo.name, nodl=args.nodl, repo=repo, overwrite=args.overwrite)
			future = executor.submit(func)
			futures.append(future)
	for result in concurrent.futures.as_completed(futures):
		print(f'[fut] res: {result.result()}')
	if args.debug:
		print(f'[finish] time {time() - starttime}')

if __name__ == '__main__':
	print(f'[main] {inspect.stack()[0][3]}')
	parser = argparse.ArgumentParser(description="github clone user")
	parser.add_argument("--user", nargs="?", default=".", help="github.com username", required=True, action="store")
	parser.add_argument("--path", nargs="?", default=".", help="destination path", required=True, action="store")
	parser.add_argument('--forks', dest='forks', action="store_true", default=False, help='include forks')
	parser.add_argument('--recursive', dest='recursive', action="store_true", default=False, help='recursive mode')
	parser.add_argument('--debug', dest='debug', action="store_true", default=False, help='debug')
	parser.add_argument('--nodl', dest='nodl', action="store_true", default=False, help='dont download - debug only')
	parser.add_argument('--overwrite', dest='overwrite', action="store_true", default=False, help='overwrite existing folders')
	args = parser.parse_args()
	main(args)