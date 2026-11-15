"""Put a pinned Mini Fighter 2.0 game build into game/v2web (the app bundles it through build/make_web.py).
    python3 build/update_game.py /path/to/minifighter-source [commit, default: HEAD of its checked-out branch]
Builds from `git archive <commit>` in a temporary folder (never from the working tree, so uncommitted work of others
is not shipped): MF_V2=1 game/tools/build.py, then game/tools/split_web.py. Writes game/SOURCE.txt with the commit."""
import os, shutil, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
src = sys.argv[1]
ref = sys.argv[2] if len(sys.argv) > 2 else 'HEAD'
commit = subprocess.run(['git', '-C', src, 'rev-parse', ref], capture_output=True, text=True, check=True).stdout.strip()
tmp = tempfile.mkdtemp(prefix='mfgame_')
try:
    arch = subprocess.run(['git', '-C', src, 'archive', commit, 'game'], capture_output=True, check=True).stdout
    subprocess.run(['tar', '-x', '-C', tmp], input=arch, check=True)
    env = dict(os.environ, MF_V2='1')
    subprocess.run([sys.executable, os.path.join(tmp, 'game', 'tools', 'build.py')], env=env, check=True)
    subprocess.run([sys.executable, os.path.join(tmp, 'game', 'tools', 'split_web.py')], check=True)
    out = os.path.join(ROOT, 'game', 'v2web')
    shutil.rmtree(out, ignore_errors=True)
    shutil.copytree(os.path.join(tmp, 'game', 'dist', 'v2web'), out)
    when = subprocess.run(['git', '-C', src, 'show', '-s', '--format=%ci', commit], capture_output=True, text=True).stdout.strip()
    open(os.path.join(ROOT, 'game', 'SOURCE.txt'), 'w').write(
        f'{commit} minifighter-source ({when})\n'
        'Built with: git archive of that commit, MF_V2=1 python3 game/tools/build.py && python3 game/tools/split_web.py\n'
        'Rebuild: python3 build/update_game.py /path/to/minifighter-source [commit]\n')
    print('game/v2web <-', commit)
finally:
    shutil.rmtree(tmp, ignore_errors=True)
