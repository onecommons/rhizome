dojo.provide("rhizome.data.Result");
dojo.require("dojo.lang.declare");
dojo.require("dojo.experimental");

/* summary:
 *   This is an abstract API used by data provider implementations.  
 *   This file defines methods signatures and intentionally leaves all the
 *   methods unimplemented.
 */
dojo.experimental("rhizome.data.Result");

dojo.declare("rhizome.data.Result", null, {
    
        initializer : function(query, store, keywordArgs) {
            this.fromKwArgs(keywordArgs || {});    
            this.result = null;
            this.resultMetadata = null;
            this._length = -1;//-1 until completion 
            this._store = store;
            this.query = query;
            
            this._aborted = false;
            this._abortFunc = null;
        },

	getLength:
		function() {
		/* summary:
		 *   Returns an integer -- the number of items in the result list.
		 *   Returns -1 if the length is not known when the method is called.
		 */
			return this._length; // integer
		},

	getStore:
		function() {
		/* summary:
		 *   Returns the datastore object that created this result list
		 */
			return this._store; // an object that implements dojo.data.Read
		},


	/** Whether the request should be made synchronously */
	sync: true,
		
	// events stuff
	oncompleted: function(type,  request) { },
	onerror: function(type, error){ },	
	//note: onnext not defined here
	
	//timeout: function(type){ }, todo: support this
	//timeoutSeconds: 0, todo: support this
		
	// the abort method needs to be filled in by the transport that accepts the
	// bind() request
	abort:
		function() {
		    this._aborted = true;
		    if (this._abortFunc)
		        this._abortFunc();
		},
	
	fromKwArgs: function(kwArgs){	                
		if (typeof kwArgs.saveResult == "undefined") {		      
		        this.saveResult = kwArgs.onnext ? false : true;
		}
				
		dojo.lang.mixin(this, kwArgs);
	}

});
