"""Set manual App Store signing on the App target's Release config only (package targets stay unsigned-by-default)."""
import re, sys
team, profile = sys.argv[1], sys.argv[2]
p = 'ios/App/App.xcodeproj/project.pbxproj'
s = open(p, encoding='utf8').read()
blocks = list(re.finditer(r'buildSettings = \{(.*?)\n\t\t\t\};\n\t\t\tname = Release;', s, re.S))
tgt = [b for b in blocks if 'PRODUCT_BUNDLE_IDENTIFIER = com.sapirproductions.minifighter;' in b.group(1)]
assert len(tgt) == 1, 'App Release config not found'
b = tgt[0]
body = re.sub(r'\n\t\t\t\t(CODE_SIGN_STYLE|CODE_SIGN_IDENTITY|"CODE_SIGN_IDENTITY\[sdk=iphoneos\*\]"|DEVELOPMENT_TEAM|PROVISIONING_PROFILE_SPECIFIER) = [^\n]*;', '', b.group(1))
body += (f'\n\t\t\t\tCODE_SIGN_STYLE = Manual;\n\t\t\t\tCODE_SIGN_IDENTITY = "Apple Distribution";'
         f'\n\t\t\t\t"CODE_SIGN_IDENTITY[sdk=iphoneos*]" = "Apple Distribution";'
         f'\n\t\t\t\tDEVELOPMENT_TEAM = {team};\n\t\t\t\tPROVISIONING_PROFILE_SPECIFIER = "{profile}";')
s = s[:b.start(1)] + body + s[b.end(1):]
open(p, 'w', encoding='utf8').write(s)
print('App Release: manual signing with', profile)
