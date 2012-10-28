import time, appscript

safari = appscript.app('Safari')
document = safari.make(new = appscript.k.document)
window, = [i for i in appscript.app('Safari').windows.get() if i.document.get() == document] # We need to get at the tab because the the document reference get's invalid as soon as a new page get's loaded.
tab = window.tabs[0].get()

start_time = time.time()

tab.URL.set('http://www.youtube.com/watch?v=MMkwevlNthQ&feature=g-vrec')

while time.time() < start_time + 1:
	print(tab.do_JavaScript('document.title'), tab.do_JavaScript('document.location.href'))
