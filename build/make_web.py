"""App web build: the game html + offline fonts + Android back button. Output: www/index.html"""
import re,base64,os,sys
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
args=[a for a in sys.argv[1:] if not a.startswith('--')]
src=args[0] if args else os.path.join(ROOT,'game','index.html')
TEST_ADS='--test-ads' in sys.argv
s=open(src,encoding='utf8').read()
faces=[]
def fs(pkg,fam,weights):
    d=os.path.join(ROOT,'node_modules','@fontsource',pkg)
    for w in weights:
        css=open(os.path.join(d,f'{w}.css')).read()
        for blk in re.findall(r'@font-face\s*{[^}]*}',css):
            if not re.search(r'files/[^)]*-(hebrew|latin)-%d-normal\.woff2'%w,blk):continue
            f=re.search(r'url\(\./(files/[^)]*\.woff2)\)',blk).group(1)
            ur=re.search(r'unicode-range:\s*([^;]+);',blk).group(1)
            b=base64.b64encode(open(os.path.join(d,f),'rb').read()).decode()
            faces.append(f"@font-face{{font-family:'{fam}';font-style:normal;font-weight:{w};font-display:block;src:url(data:font/woff2;base64,{b}) format('woff2');unicode-range:{ur}}}")
fs('rubik','Rubik',[400,500,600,700,800,900]);fs('secular-one','Secular One',[400])
s=re.sub(r'<link rel="preconnect" href="https://fonts.googleapis.com">\s*','',s)
s=re.sub(r'<link href="https://fonts.googleapis.com/css2[^>]*>','<style>'+''.join(faces)+'</style>',s)
assert 'fonts.googleapis' not in s
# test build: Google test ads (safe to tap while testing on your own phone)
if TEST_ADS:
    assert 'test:false,interGapMs' in s
    s=s.replace('test:false,interGapMs','test:true,interGapMs',1)
# app: native immersive mode replaces the browser fullscreen request; hide that setting
s=s.replace("function goFull(){","function goFull(){if(window.Capacitor&&Capacitor.isNativePlatform&&Capacitor.isNativePlatform())return;",1)
s=s.replace("${tg('full','מסך מלא בטלפון',CFG.full)}","${window.Capacitor?'':tg('full','מסך מלא בטלפון',CFG.full)}",1)
bridge='''<script>
// Android back button: closes menus step by step, pauses a running fight, leaves the app from the title screen
(function(){const C=window.Capacitor;if(!C||!C.registerPlugin)return;const App=C.registerPlugin('App');
 App.addListener('backButton',()=>{try{
  if(menuOpen()){if(typeof SCREEN!=='undefined'&&SCREEN==='title'&&!(G&&G.paused)&&!(typeof NET!=='undefined'&&NET.want)){App.exitApp();return;}if(BACK){BACK();return;}if(G&&G.paused){togglePause();return;}title();return;}
  if(G&&G.mode!=='demo'&&!G.over){togglePause();return;}
  if(typeof NET!=='undefined'&&NET.want&&SCREEN==='title'){mpMenu();return;}
 }catch(e){}});
 App.addListener('pause',()=>{try{if(G&&G.net)return;if(G&&G.mode!=='demo'&&!G.paused&&!G.over&&!menuOpen())togglePause();}catch(e){}});
 App.addListener('resume',()=>{try{if(typeof NET!=='undefined'&&NET.want&&!(NET.ws&&NET.ws.readyState<=1)){NET.tries=0;netOpen();}}catch(e){}});})();
</script></body></html>'''
assert s.rstrip().endswith('</body></html>')
s=s.rstrip()[:-len('</body></html>')]+bridge
os.makedirs(os.path.join(ROOT,'www'),exist_ok=True)
open(os.path.join(ROOT,'www','index.html'),'w',encoding='utf8').write(s)
print('www/index.html',len(s)//1024,'KB, fonts:',len(faces),'| ads:','TEST' if TEST_ADS else 'LIVE')
