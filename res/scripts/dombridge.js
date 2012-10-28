(function ($) {
	$.noConflict();
	
	// Setting this stuff here so we can poll the $.dombridge.loaded property.
	$.dombridge = { }
	$.dombridge.handles = []
	$.dombridge.loaded = false
	
	function reapDom(elem) {
		var res;
		
		if (elem.nodeType == document.ELEMENT_NODE) {
			var name = elem.localName;
			var attrs = [];
			var children = []
			
			for (var i = 0; i < elem.attributes.length; i += 1) {
				var node = elem.attributes[i];
				
				attrs.push([node.name, node.value]);
			}
			
			if (elem.contentDocument !== undefined)
				elem = elem.contentDocument;
			
			for (var i = 0; i < elem.childNodes.length; i += 1) {
				var node = elem.childNodes[i];
				var res = reapDom(node);
				
				if (res !== null)
					children.push(res);
			}
			
			res = { 'name': name, 'attributes': attrs, 'children': children };
		} else if (elem.nodeType == document.TEXT_NODE) {
			res = { 'text': elem.data };
		} else if (elem.nodeType == document.DOCUMENT_NODE) {
			return reapDom(elem.documentElement);
		} else {
			return null;
		}
		
		res.handle = $.dombridge.handles.length
		$.dombridge.handles.push(elem)
		
		return res
	}
	
	$(function () {
		$.dombridge.root = reapDom(document);
		$.dombridge.loaded = true
	})
}) (jQuery)
