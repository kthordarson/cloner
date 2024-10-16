#!/usr/bin/env python3
from github import Github
from github.GithubException import BadCredentialsException
import argparse
from functools import partial
import concurrent.futures
from subprocess import Popen, PIPE
from shutil import rmtree
import os
import stat
from time import time
from pathlib import Path
from loguru import logger

GITHUBCLONERTOKEN = os.getenv('GITHUBCLONERTOKEN')
GITBINARY = '/usr/bin/git'


def removepath(directory):
	directory = Path(directory)
	for item in directory.iterdir():
		if item.is_dir():
			try:
				os.chmod(item, stat.S_IWRITE)
				rmtree(item, ignore_errors=True)
			# os.rmdir(item)
			except Exception as e:
				logger.error(f'Error {e} while removing {item}')
		# rmtree(item, ignore_errors=True)
		else:
			os.chmod(item, stat.S_IWRITE)
			item.unlink()
	directory.rmdir()


def githubdownloader(destpath=None, debug=False, recursive=False, nodl=False, repo=None, url=None, overwrite=False):
	logger.debug(f'[ghdl] cloning {repo.name}')
	start_time = time()
	if repo is None:
		return -1
	if recursive:
		gitcmd = [GITBINARY, 'clone', '--quiet', '--recursive', url, destpath]
	else:
		gitcmd = [GITBINARY, 'clone', '--quiet', url, destpath]
	if not nodl:
		if not os.path.exists(destpath):
			p = Popen(gitcmd, shell=False, stdout=PIPE, stderr=PIPE)
			status = p.wait()
			p.communicate()
			root_directory = Path(destpath)
			reposize = sum(f.stat().st_size for f in root_directory.glob('**/*') if f.is_file())
			if debug:
				logger.debug(f'[ghdl] done {repo.name} status {status} time: {time() - start_time:.2f} size: {reposize}')
			rettime = f'{time() - start_time:.2f}'
			return {'name': repo.name, 'size': reposize, 'time': rettime}
		elif os.path.exists(destpath) and overwrite:
			logger.debug(f'[ghdl] {repo.name} {destpath} exists, overwriting {overwrite}')
			try:
				if os.path.exists(destpath):
					removepath(Path(destpath))
			except OSError as e:
				logger.debug(f'[ghdl] error {e} {destpath}')
				rettime = f'{time() - start_time:.2f}'
				return {'name': repo.name, 'time': rettime}
			else:
				p = Popen(gitcmd, shell=False, stdout=PIPE, stderr=PIPE)
				p.wait()
				p.communicate()
				rettime = f'{time() - start_time:.2f}'
				return {'name': repo.name, 'time': rettime}
		elif os.path.exists(destpath):
			logger.debug(f'[ghdl] {repo.name} {destpath} already exists, skipping')
			rettime = f'{time() - start_time:.2f}'
			return {'name': repo.name, 'time': rettime}
		else:
			logger.debug(f'[ghdl] {repo.name} {destpath}  skipping')
			rettime = f'{time() - start_time:.2f}'
			return {'name': repo.name, 'time': rettime}
	else:
		logger.debug(f'[ghdl] {repo.name} nodl set {destpath} not downloading')
		rettime = f'{time() - start_time:.2f}'
		return {'name': repo.name, 'time': rettime}


def get_user_repos(git_username=None, gh=None, forks=False, debug=False, lang_filter=None):
	repos = None
	try:
		g_user_sesssion = gh.get_user(git_username)
	except BadCredentialsException as e:
		logger.error(f'[get_user_repos] autherr {e}')
		raise e
	g_repos = g_user_sesssion.get_repos()
	# return g_repos
	if forks:
		repos = [r for r in g_repos]
	else:
		repos = [r for r in g_repos if not r.fork]
	logger.debug(f'[gur] u:{git_username} forks:{forks} ghrepos:{g_repos.totalCount} r:{len(repos)}')
	return repos


def main(args):
	starttime = time()
	github = Github(GITHUBCLONERTOKEN)
	try:
		repo_list = get_user_repos(args.user, gh=github, debug=args.debug)
	except BadCredentialsException as e:
		logger.error(f'[main] autherr {e}')
		return
	logger.debug(f'[{args.user}] {len(repo_list)} repos')
	futures = []
	with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
		for repo in repo_list:
			dlpath = os.path.join(args.destpath, args.user, repo.name)
			func = partial(githubdownloader, url=repo.clone_url, destpath=dlpath, debug=args.debug, nodl=args.nodl, repo=repo, overwrite=args.overwrite)
			future = executor.submit(func)
			futures.append(future)
	for result in concurrent.futures.as_completed(futures):
		logger.debug(f'[fut] res: {result.result()["name"]} {result.result()["size"]} {result.result()["time"]}')
	if args.debug:
		logger.debug(f'[finish] time {time() - starttime:.2f}')


if __name__ == '__main__':
	parser = argparse.ArgumentParser(description="github clone user")
	parser.add_argument("--user", nargs="?", default=".", help="github.com username", required=True, action="store")
	parser.add_argument("--destpath", nargs="?", default=".", help="destination path", required=True, action="store")
	parser.add_argument('--forks', dest='forks', action="store_true", default=False, help='include forks')
	parser.add_argument('--recursive', dest='recursive', action="store_true", default=False, help='recursive mode')
	parser.add_argument('--debug', dest='debug', action="store_true", default=True, help='debug')
	parser.add_argument('--nodl', dest='nodl', action="store_true", default=False, help='dont download - debug only')
	parser.add_argument('--overwrite', dest='overwrite', action="store_true", default=False, help='overwrite existing folders')
	args = parser.parse_args()
	main(args)
