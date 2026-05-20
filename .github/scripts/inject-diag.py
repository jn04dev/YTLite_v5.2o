#!/usr/bin/env python3
"""
Diagnostic injection for ytp_diag.yml builds.

Patches the cloned YTLite.x source with file-based logging hooks plus
the speculative shorts shelf size collapse. Lives in a separate file
because the inline workflow heredoc exceeded GitHub Actions' 21000-char
max expression length.

Usage: python3 inject-diag.py <path-to-YTLite.x>
"""
import pathlib
import re
import sys

if len(sys.argv) != 2:
    raise SystemExit(f"usage: {sys.argv[0]} <path-to-YTLite.x>")

p = pathlib.Path(sys.argv[1])
src = p.read_text()

# Injection 0: file-based logging helper, inserted before the first %hook.
helper = (
    '\n'
    '// [YTLite-DIAG] TEMPORARY — file-based logging helper.\n'
    '// Writes to NSDocumentDirectory/ytlite-diag.log. Retrieve via\n'
    '// Finder File Sharing on the diag IPA (UIFileSharingEnabled is\n'
    '// set on the IPA in a later workflow step).\n'
    '#import <stdio.h>\n'
    '#import <stdarg.h>\n'
    '#import <unistd.h>\n'
    'static FILE *_yld_fp = NULL;\n'
    'static NSLock *_yld_lock = nil;\n'
    'static char _ytlite_shorts_assoc_key;\n'
    'static void _yld_init(void) {\n'
    '    static dispatch_once_t once;\n'
    '    dispatch_once(&once, ^{\n'
    '        _yld_lock = [[NSLock alloc] init];\n'
    '        NSArray *paths = NSSearchPathForDirectoriesInDomains(NSDocumentDirectory, NSUserDomainMask, YES);\n'
    '        if (paths.count == 0) return;\n'
    '        NSString *path = [[paths firstObject] stringByAppendingPathComponent:@"ytlite-diag.log"];\n'
    '        _yld_fp = fopen([path UTF8String], "a");\n'
    '        if (_yld_fp) {\n'
    '            setvbuf(_yld_fp, NULL, _IOLBF, 0);\n'
    '            NSString *startup = [NSString stringWithFormat:@"--- ytlite-diag start %@ bundle=%@ pid=%d ---\\n",\n'
    '                                  [NSDate date], [[NSBundle mainBundle] bundleIdentifier], getpid()];\n'
    '            fputs([startup UTF8String], _yld_fp);\n'
    '            fflush(_yld_fp);\n'
    '        }\n'
    '    });\n'
    '}\n'
    'static void _yld(NSString *fmt, ...) NS_FORMAT_FUNCTION(1, 2);\n'
    'static void _yld(NSString *fmt, ...) {\n'
    '    _yld_init();\n'
    '    if (!_yld_fp) return;\n'
    '    va_list args;\n'
    '    va_start(args, fmt);\n'
    '    NSString *msg = [[NSString alloc] initWithFormat:fmt arguments:args];\n'
    '    va_end(args);\n'
    '    [_yld_lock lock];\n'
    '    if (_yld_fp) {\n'
    '        fputs([msg UTF8String], _yld_fp);\n'
    '        fputc(\'\\n\', _yld_fp);\n'
    '        fflush(_yld_fp);\n'
    '    }\n'
    '    [_yld_lock unlock];\n'
    '}\n'
    '\n'
)
m = re.search(r"^%hook ", src, re.MULTILINE)
if not m:
    raise SystemExit("No %hook found in YTLite.x; cannot place helper")
src = src[:m.start()] + helper + src[m.start():]

# Injection 1: unfiltered file-logging in YTAsyncCollectionView hook
anchor1 = (
    "// Remove Premium Pop-up, Horizontal Video Carousel and Shorts (https://github.com/MiRO92/YTNoShorts)\n"
    "%hook YTAsyncCollectionView\n"
    "- (id)cellForItemAtIndexPath:(NSIndexPath *)indexPath {\n"
    "    UICollectionViewCell *cell = %orig;\n"
)
if anchor1 not in src:
    raise SystemExit("YTAsyncCollectionView hook anchor not found")
injected1 = (
    anchor1
    + '\n'
    '    // [YTLite-DIAG] TEMPORARY — unfiltered cell logging via _yld.\n'
    '    {\n'
    '        NSString *cellCls = NSStringFromClass([cell class]);\n'
    '        NSString *cellID = cell.accessibilityIdentifier ?: @"<nil>";\n'
    '        NSString *nodeCls = @"<no-node>";\n'
    '        NSString *nodeID = @"<no-node>";\n'
    '        if ([cell respondsToSelector:@selector(node)]) {\n'
    '            id node = [(id)cell node];\n'
    '            if (node) {\n'
    '                nodeCls = NSStringFromClass([node class]);\n'
    '                if ([node respondsToSelector:@selector(accessibilityIdentifier)]) {\n'
    '                    nodeID = [node accessibilityIdentifier] ?: @"<nil>";\n'
    '                }\n'
    '            }\n'
    '        }\n'
    '        _yld(@"[YT] sec=%ld row=%ld cellCls=%@ cellID=%@ nodeCls=%@ nodeID=%@", (long)indexPath.section, (long)indexPath.row, cellCls, cellID, nodeCls, nodeID);\n'
    '    }\n'
)
src = src.replace(anchor1, injected1)

# Injection 2: append a new %hook block for ASCollectionView at the end of file
new_hook = (
    '\n'
    '// [YTLite-DIAG] TEMPORARY hook on the AsyncDisplayKit base class to catch\n'
    '// home-feed cells in case YT 21.x uses ASCollectionView directly rather\n'
    '// than YTAsyncCollectionView. The guard avoids double-logging when the\n'
    '// instance is actually a YTAsyncCollectionView (the subclass hook fires\n'
    '// first due to ObjC dispatch).\n'
    '%hook ASCollectionView\n'
    '- (id)cellForItemAtIndexPath:(NSIndexPath *)indexPath {\n'
    '    UICollectionViewCell *cell = %orig;\n'
    '    NSString *viewCls = NSStringFromClass([self class]);\n'
    '    if (![viewCls isEqualToString:@"YTAsyncCollectionView"]) {\n'
    '        NSString *cellCls = NSStringFromClass([cell class]);\n'
    '        NSString *cellID = cell.accessibilityIdentifier ?: @"<nil>";\n'
    '        NSString *nodeCls = @"<no-node>";\n'
    '        NSString *nodeID = @"<no-node>";\n'
    '        if ([cell respondsToSelector:@selector(node)]) {\n'
    '            id node = [(id)cell node];\n'
    '            if (node) {\n'
    '                nodeCls = NSStringFromClass([node class]);\n'
    '                if ([node respondsToSelector:@selector(accessibilityIdentifier)]) {\n'
    '                    nodeID = [node accessibilityIdentifier] ?: @"<nil>";\n'
    '                }\n'
    '            }\n'
    '        }\n'
    '        _yld(@"[AS] viewCls=%@ sec=%ld row=%ld cellCls=%@ cellID=%@ nodeCls=%@ nodeID=%@", viewCls, (long)indexPath.section, (long)indexPath.row, cellCls, cellID, nodeCls, nodeID);\n'
    '    }\n'
    '    return cell;\n'
    '}\n'
    '%end\n'
)
src = src.rstrip() + '\n' + new_hook

# Injection 3: append UICollectionView base-class dequeue hook (the catchall).
catchall = (
    '\n'
    '// [YTLite-DIAG] TEMPORARY catchall hook on UICollectionView base class.\n'
    '// Every UICollectionView subclass uses this dequeue method, so this is\n'
    '// the broadest possible net for cell rendering. Logs view class, reuse\n'
    '// identifier, indexPath, cell class, and node class if present.\n'
    '%hook UICollectionView\n'
    '- (UICollectionViewCell *)dequeueReusableCellWithReuseIdentifier:(NSString *)identifier forIndexPath:(NSIndexPath *)indexPath {\n'
    '    UICollectionViewCell *cell = %orig;\n'
    '    NSString *viewCls = NSStringFromClass([self class]);\n'
    '    NSString *cellCls = cell ? NSStringFromClass([cell class]) : @"<nil>";\n'
    '    NSString *nodeCls = @"<no-node>";\n'
    '    NSString *nodeID = @"<no-node>";\n'
    '    if (cell && [cell respondsToSelector:@selector(node)]) {\n'
    '        id node = [(id)cell node];\n'
    '        if (node) {\n'
    '            nodeCls = NSStringFromClass([node class]);\n'
    '            if ([node respondsToSelector:@selector(accessibilityIdentifier)]) {\n'
    '                nodeID = [node accessibilityIdentifier] ?: @"<nil>";\n'
    '            }\n'
    '        }\n'
    '    }\n'
    '    _yld(@"[DEQ] viewCls=%@ reuseID=%@ sec=%ld row=%ld cellCls=%@ nodeCls=%@ nodeID=%@", viewCls, identifier, (long)indexPath.section, (long)indexPath.row, cellCls, nodeCls, nodeID);\n'
    '\n'
    '    if (cell && [cell respondsToSelector:@selector(node)]) {\n'
    '        NSInteger sec = indexPath.section;\n'
    '        NSInteger row = indexPath.row;\n'
    '        NSString *rid = identifier ? [identifier copy] : @"<nil>";\n'
    '        NSString *vcls = viewCls ? [viewCls copy] : @"<nil>";\n'
    '        __weak UICollectionViewCell *weakCell = cell;\n'
    '        dispatch_async(dispatch_get_main_queue(), ^{\n'
    '            UICollectionViewCell *c = weakCell;\n'
    '            if (!c) return;\n'
    '            if (![c respondsToSelector:@selector(node)]) return;\n'
    '            id node = [(id)c node];\n'
    '            if (!node) return;\n'
    '            NSString *ncls = NSStringFromClass([node class]);\n'
    '            NSString *nid = @"<nil>";\n'
    '            if ([node respondsToSelector:@selector(accessibilityIdentifier)]) {\n'
    '                nid = [node accessibilityIdentifier] ?: @"<nil>";\n'
    '            }\n'
    '            _yld(@"[NDQ] viewCls=%@ reuseID=%@ sec=%ld row=%ld nodeCls=%@ nodeID=%@", vcls, rid, (long)sec, (long)row, ncls, nid);\n'
    '        });\n'
    '    }\n'
    '    return cell;\n'
    '}\n'
    '%end\n'
)
src = src.rstrip() + '\n' + catchall

# Injection 4: %ctor block — startup marker + class diagnostics
ctor_block = (
    '\n'
    '// [YTLite-DIAG] TEMPORARY ctor: writes startup marker + class-existence diagnostics.\n'
    '%ctor {\n'
    '    _yld_init();\n'
    '    _yld(@"[CTRL] ytlite tweak ctor fired pid=%d", getpid());\n'
    '    _yld(@"[CTRL] cls YTAsyncCollectionView: %@", objc_lookUpClass("YTAsyncCollectionView") ? @"FOUND" : @"NIL");\n'
    '    _yld(@"[CTRL] cls ASCollectionView: %@", objc_lookUpClass("ASCollectionView") ? @"FOUND" : @"NIL");\n'
    '    _yld(@"[CTRL] cls UICollectionView: %@", objc_lookUpClass("UICollectionView") ? @"FOUND" : @"NIL");\n'
    '    _yld(@"[CTRL] cls _ASCollectionViewCell: %@", objc_lookUpClass("_ASCollectionViewCell") ? @"FOUND" : @"NIL");\n'
    '    _yld(@"[CTRL] cls YTReelShelfCell: %@", objc_lookUpClass("YTReelShelfCell") ? @"FOUND" : @"NIL");\n'
    '    _yld(@"[CTRL] cls YTHorizontalShelfCell: %@", objc_lookUpClass("YTHorizontalShelfCell") ? @"FOUND" : @"NIL");\n'
    '    _yld(@"[CTRL] cls YTShelfCell: %@", objc_lookUpClass("YTShelfCell") ? @"FOUND" : @"NIL");\n'
    '    _yld(@"[CTRL] cls YTHorizontalCardListCell: %@", objc_lookUpClass("YTHorizontalCardListCell") ? @"FOUND" : @"NIL");\n'
    '    _yld(@"[CTRL] cls YTHorizontalButtonListCell: %@", objc_lookUpClass("YTHorizontalButtonListCell") ? @"FOUND" : @"NIL");\n'
    '    _yld(@"[CTRL] cls YTFeedEntryCell: %@", objc_lookUpClass("YTFeedEntryCell") ? @"FOUND" : @"NIL");\n'
    '    _yld(@"[CTRL] cls YTVideoFeedEntryCell: %@", objc_lookUpClass("YTVideoFeedEntryCell") ? @"FOUND" : @"NIL");\n'
    '    {\n'
    '        Class _yer = objc_lookUpClass("YTIElementRenderer");\n'
    '        if (_yer) {\n'
    '            unsigned int _cnt = 0;\n'
    '            Method *_ml = class_copyMethodList(_yer, &_cnt);\n'
    '            _yld(@"[CTRL] YTIElementRenderer direct methods (count=%u, parent=%@):", _cnt, NSStringFromClass([_yer superclass]));\n'
    '            for (unsigned int i = 0; i < _cnt; i++) {\n'
    '                _yld(@"[CTRL]   - %@", NSStringFromSelector(method_getName(_ml[i])));\n'
    '            }\n'
    '            if (_ml) free(_ml);\n'
    '        }\n'
    '    }\n'
    '    {\n'
    '        NSArray *_chainClasses = @[@"YTAsyncCollectionView", @"ASCollectionView", @"ELMCellNode", @"ELMNodeController", @"ELMContainerNode"];\n'
    '        for (NSString *clsName in _chainClasses) {\n'
    '            Class _c = objc_lookUpClass([clsName UTF8String]);\n'
    '            if (!_c) {\n'
    '                _yld(@"[CTRL] chain %@: NOT FOUND", clsName);\n'
    '                continue;\n'
    '            }\n'
    '            NSMutableArray *_chain = [NSMutableArray array];\n'
    '            Class _walk = _c;\n'
    '            while (_walk) {\n'
    '                [_chain addObject:NSStringFromClass(_walk)];\n'
    '                _walk = class_getSuperclass(_walk);\n'
    '            }\n'
    '            _yld(@"[CTRL] chain %@: %@", clsName, [_chain componentsJoinedByString:@" -> "]);\n'
    '        }\n'
    '    }\n'
    '}\n'
)
src = src.rstrip() + '\n' + ctor_block

# Injection 5: ELMD dedupe-log inside the existing elementData hook
anchor5 = "    NSString *description = [self description];\n"
if anchor5 not in src:
    raise SystemExit("elementData anchor for ELMD injection not found")
if src.count(anchor5) != 1:
    raise SystemExit("elementData anchor not unique; refusing to inject")
elmd_inject = (
    anchor5
    + '\n'
    '    // [YTLite-DIAG] TEMPORARY: dedupe-log every unique description value.\n'
    '    if (description) {\n'
    '        static NSMutableSet *_elmd_seen = nil;\n'
    '        static NSLock *_elmd_lock = nil;\n'
    '        static dispatch_once_t _elmd_once;\n'
    '        dispatch_once(&_elmd_once, ^{\n'
    '            _elmd_seen = [NSMutableSet set];\n'
    '            _elmd_lock = [[NSLock alloc] init];\n'
    '        });\n'
    '        [_elmd_lock lock];\n'
    '        BOOL _isNew = ![_elmd_seen containsObject:description];\n'
    '        if (_isNew) [_elmd_seen addObject:[description copy]];\n'
    '        [_elmd_lock unlock];\n'
    '        if (_isNew) {\n'
    '            _yld(@"[ELMD] desc=%@", description);\n'
    '        }\n'
    '    }\n'
)
src = src.replace(anchor5, elmd_inject)

# Injection 6: SZE2 — element-description-based shorts collapse + diagnostics inside sizeForElement
anchor6 = (
    '%hook ASCollectionView\n'
    '- (CGSize)sizeForElement:(ASCollectionElement *)element {\n'
    '    if ([self.accessibilityIdentifier isEqualToString:@"id.video.scrollable_action_bar"]) {'
)
if anchor6 not in src:
    raise SystemExit("sizeForElement anchor for SZE2 injection not found")
sze_inject = (
    '%hook ASCollectionView\n'
    '- (CGSize)sizeForElement:(ASCollectionElement *)element {\n'
    '    {\n'
    '        // [YTLite-DIAG] SZE2 — element-description-based shorts collapse + diagnosis.\n'
    '        ASCellNode *_szNode = [element node];\n'
    '        Class _szNodeCls = _szNode ? [_szNode class] : nil;\n'
    '        NSString *_szNodeClsName = _szNodeCls ? NSStringFromClass(_szNodeCls) : @"<nil>";\n'
    '        id _szElement = nil;\n'
    '        @try {\n'
    '            if (_szNode && class_getInstanceVariable(_szNodeCls, "_element")) {\n'
    '                _szElement = [_szNode valueForKey:@"_element"];\n'
    '            }\n'
    '        } @catch (NSException *_e) { _szElement = nil; }\n'
    '        NSString *_szElemCls = _szElement ? NSStringFromClass([_szElement class]) : @"<nil>";\n'
    '        NSString *_szDesc = nil;\n'
    '        if (_szElement) {\n'
    '            @try { _szDesc = [_szElement description]; } @catch (NSException *_e) { _szDesc = nil; }\n'
    '        }\n'
    '        BOOL _szMatched = NO;\n'
    '        NSString *_szMatchedToken = nil;\n'
    '        if (_szDesc) {\n'
    '            NSArray *_szTokens = @[@"shorts_video_cell.eml", @"shorts_grid_shelf_footer", @"youtube_shorts_24"];\n'
    '            for (NSString *_tok in _szTokens) {\n'
    '                if ([_szDesc containsString:_tok]) {\n'
    '                    _szMatched = YES;\n'
    '                    _szMatchedToken = _tok;\n'
    '                    break;\n'
    '                }\n'
    '            }\n'
    '        }\n'
    '        static NSMutableSet *_sze2_seen = nil;\n'
    '        static NSLock *_sze2_lock = nil;\n'
    '        static dispatch_once_t _sze2_once;\n'
    '        dispatch_once(&_sze2_once, ^{\n'
    '            _sze2_seen = [NSMutableSet set];\n'
    '            _sze2_lock = [[NSLock alloc] init];\n'
    '        });\n'
    '        NSString *_szKey = [NSString stringWithFormat:@"%@|%@|%d|%@", _szNodeClsName, _szElemCls, _szMatched, _szMatchedToken ?: @"(none)"];\n'
    '        [_sze2_lock lock];\n'
    '        BOOL _szIsNew = ![_sze2_seen containsObject:_szKey];\n'
    '        if (_szIsNew) [_sze2_seen addObject:[_szKey copy]];\n'
    '        [_sze2_lock unlock];\n'
    '        if (_szIsNew) {\n'
    '            _yld(@"[SZE2] nodeCls=%@ elemCls=%@ matched=%@ token=%@", _szNodeClsName, _szElemCls, _szMatched ? @"YES" : @"NO", _szMatchedToken ?: @"-");\n'
    '            static NSMutableSet *_elemIvarsLogged = nil;\n'
    '            static dispatch_once_t _eivOnce;\n'
    '            dispatch_once(&_eivOnce, ^{ _elemIvarsLogged = [NSMutableSet set]; });\n'
    '            @synchronized(_elemIvarsLogged) {\n'
    '                if (_szElement && ![_elemIvarsLogged containsObject:_szElemCls]) {\n'
    '                    [_elemIvarsLogged addObject:[_szElemCls copy]];\n'
    '                    Class _ec = [_szElement class];\n'
    '                    unsigned int _eivc = 0;\n'
    '                    Ivar *_eivl = class_copyIvarList(_ec, &_eivc);\n'
    '                    _yld(@"[SZE2] elem ivars for %@ (count=%u, parent=%@):", _szElemCls, _eivc, NSStringFromClass([_ec superclass]));\n'
    '                    for (unsigned int i = 0; i < _eivc; i++) {\n'
    '                        const char *iname = ivar_getName(_eivl[i]);\n'
    '                        const char *itype = ivar_getTypeEncoding(_eivl[i]);\n'
    '                        _yld(@"[SZE2]   %s : %s", iname ? iname : "?", itype ? itype : "?");\n'
    '                    }\n'
    '                    if (_eivl) free(_eivl);\n'
    '                }\n'
    '            }\n'
    '        }\n'
    '        BOOL _szHasAssoc = NO;\n'
    '        if (_szElement) {\n'
    '            @try {\n'
    '                id _szMark = objc_getAssociatedObject(_szElement, &_ytlite_shorts_assoc_key);\n'
    '                if ([_szMark isKindOfClass:[NSNumber class]] && [(NSNumber *)_szMark boolValue]) {\n'
    '                    _szHasAssoc = YES;\n'
    '                }\n'
    '            } @catch (NSException *_e) { _szHasAssoc = NO; }\n'
    '        }\n'
    '        if (_szIsNew) {\n'
    '            _yld(@"[SZE2] hasAssoc=%@ for elemCls=%@", _szHasAssoc ? @"YES" : @"NO", _szElemCls);\n'
    '        }\n'
    '        if (ytlBool(@"hideShorts") && (_szMatched || _szHasAssoc)) {\n'
    '            return CGSizeZero;\n'
    '        }\n'
    '    }\n'
    '    if ([self.accessibilityIdentifier isEqualToString:@"id.video.scrollable_action_bar"]) {'
)
src = src.replace(anchor6, sze_inject)

# Extend shortsToRemove tokens to match stable
old_tokens = '    NSArray *shortsToRemove = @[@"shorts_shelf.eml", @"shorts_video_cell.eml", @"6Shorts"];'
new_tokens = '    NSArray *shortsToRemove = @[@"shorts_shelf.eml", @"shorts_video_cell.eml", @"6Shorts", @"shorts_grid_shelf_footer", @"youtube_shorts_24"];'
if old_tokens in src:
    src = src.replace(old_tokens, new_tokens)

# Injection 7 (diag-16): hook YTIElementRenderer initializers to mark shorts
# renderers AND their elements with objc_setAssociatedObject. The CTRL method
# list dump in diag-13 showed YTIElementRenderer has two init methods:
# initWithElement: (taking an element instance) and initWithElementData: (taking
# raw NSData). These are the bind points where we can correlate the renderer
# (whose description contains shorts tokens) with the element (which becomes
# cellNode._element at size time).
#
# When a renderer is initialized and its description matches a shorts token,
# we mark self via objc_setAssociatedObject. If initWithElement: is the
# constructor, we also mark the passed element argument — that's the same
# ELMElement instance the cell will hold in its _element ivar later. At
# sizeForElement time we check the cell's element for the association and
# return CGSizeZero on hit.
#
# The diag-15 section-list filter is removed entirely — it caused regressions
# (settings UI broken, first-launch crash) and zero SLF matches in the log.
init_hook = (
    '\n'
    '// [YTLite-DIAG] TEMPORARY: mark shorts renderers + elements at init time\n'
    '// so the SZE2 hook can collapse matching cells by associated-object lookup.\n'
    '%hook YTIElementRenderer\n'
    '- (instancetype)initWithElement:(id)element {\n'
    '    self = %orig;\n'
    '    if (self) {\n'
    '        NSString *_initDesc = nil;\n'
    '        @try { _initDesc = [self description]; } @catch (NSException *_e) { _initDesc = nil; }\n'
    '        BOOL _initMatched = NO;\n'
    '        NSString *_initToken = nil;\n'
    '        if (_initDesc) {\n'
    '            NSArray *_initTokens = @[@"youtube_shorts_24", @"shorts_grid_shelf_footer", @"shorts_video_cell.eml"];\n'
    '            for (NSString *_tok in _initTokens) {\n'
    '                if ([_initDesc containsString:_tok]) {\n'
    '                    _initMatched = YES;\n'
    '                    _initToken = _tok;\n'
    '                    break;\n'
    '                }\n'
    '            }\n'
    '        }\n'
    '        if (_initMatched) {\n'
    '            objc_setAssociatedObject(self, &_ytlite_shorts_assoc_key, @YES, OBJC_ASSOCIATION_RETAIN_NONATOMIC);\n'
    '            if (element) {\n'
    '                objc_setAssociatedObject(element, &_ytlite_shorts_assoc_key, @YES, OBJC_ASSOCIATION_RETAIN_NONATOMIC);\n'
    '            }\n'
    '        }\n'
    '        static NSMutableSet *_init1_seen = nil;\n'
    '        static NSLock *_init1_lock = nil;\n'
    '        static dispatch_once_t _init1_once;\n'
    '        dispatch_once(&_init1_once, ^{\n'
    '            _init1_seen = [NSMutableSet set];\n'
    '            _init1_lock = [[NSLock alloc] init];\n'
    '        });\n'
    '        NSString *_initElemCls = element ? NSStringFromClass([element class]) : @"<nil>";\n'
    '        NSString *_initKey = [NSString stringWithFormat:@"initWithElement:|elemCls=%@|matched=%d|token=%@", _initElemCls, _initMatched, _initToken ?: @"-"];\n'
    '        [_init1_lock lock];\n'
    '        BOOL _isNew = ![_init1_seen containsObject:_initKey];\n'
    '        if (_isNew) [_init1_seen addObject:[_initKey copy]];\n'
    '        [_init1_lock unlock];\n'
    '        if (_isNew) {\n'
    '            _yld(@"[INIT1] elemCls=%@ matched=%@ token=%@", _initElemCls, _initMatched ? @"YES" : @"NO", _initToken ?: @"-");\n'
    '        }\n'
    '    }\n'
    '    return self;\n'
    '}\n'
    '- (instancetype)initWithElementData:(NSData *)data {\n'
    '    self = %orig;\n'
    '    if (self) {\n'
    '        NSString *_initDesc = nil;\n'
    '        @try { _initDesc = [self description]; } @catch (NSException *_e) { _initDesc = nil; }\n'
    '        BOOL _initMatched = NO;\n'
    '        NSString *_initToken = nil;\n'
    '        if (_initDesc) {\n'
    '            NSArray *_initTokens = @[@"youtube_shorts_24", @"shorts_grid_shelf_footer", @"shorts_video_cell.eml"];\n'
    '            for (NSString *_tok in _initTokens) {\n'
    '                if ([_initDesc containsString:_tok]) {\n'
    '                    _initMatched = YES;\n'
    '                    _initToken = _tok;\n'
    '                    break;\n'
    '                }\n'
    '            }\n'
    '        }\n'
    '        if (_initMatched) {\n'
    '            objc_setAssociatedObject(self, &_ytlite_shorts_assoc_key, @YES, OBJC_ASSOCIATION_RETAIN_NONATOMIC);\n'
    '        }\n'
    '        static NSMutableSet *_init2_seen = nil;\n'
    '        static NSLock *_init2_lock = nil;\n'
    '        static dispatch_once_t _init2_once;\n'
    '        dispatch_once(&_init2_once, ^{\n'
    '            _init2_seen = [NSMutableSet set];\n'
    '            _init2_lock = [[NSLock alloc] init];\n'
    '        });\n'
    '        NSString *_initKey = [NSString stringWithFormat:@"initWithElementData:|dataLen=%lu|matched=%d|token=%@", (unsigned long)(data ? [data length] : 0), _initMatched, _initToken ?: @"-"];\n'
    '        [_init2_lock lock];\n'
    '        BOOL _isNew = ![_init2_seen containsObject:_initKey];\n'
    '        if (_isNew) [_init2_seen addObject:[_initKey copy]];\n'
    '        [_init2_lock unlock];\n'
    '        if (_isNew) {\n'
    '            _yld(@"[INIT2] dataLen=%lu matched=%@ token=%@", (unsigned long)(data ? [data length] : 0), _initMatched ? @"YES" : @"NO", _initToken ?: @"-");\n'
    '        }\n'
    '    }\n'
    '    return self;\n'
    '}\n'
    '%end\n'
)
src = src.rstrip() + '\n' + init_hook

p.write_text(src)
print("Diagnostic injections applied: helper + YT/AS/DEQ/NDQ logging + %ctor with class chains + ELMD + SZE2 (elem desc + assoc check) + token extension + INIT1/INIT2 renderer-init hooks with associated-object marking")
