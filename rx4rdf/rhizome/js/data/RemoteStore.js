dojo.provide("rhizome.data.RemoteStore");
dojo.require("rhizome.data.Result");
dojo.require("dojo.data.Read");
dojo.require("dojo.data.Write");
dojo.require("dojo.collections.Collections");
dojo.require("dojo.Deferred");
dojo.require("dojo.lang.declare");
dojo.require("dojo.json");
dojo.require("dojo.io.*");

/*
RemoteStore is an implemention the dojo.data.Read and Write APIs. 
It is designed to serve as a base class for dojo.data stores which interact with stateless web services that can querying and modifying record-oriented data.
Its features include asynchronous and synchronous querying and saving; caching of queries; transactions; and datatype mapping.

Derived classes from RemoteStore should implemen the following methods:

    _setupQueryRequest(query, queryKwArgs, requestKw) 

    This function prepares the query request by populating requestKw, 
    an associative array that will be passed to dojo.io.bind.

    _resultToQueryData(responseData) 

    Converts the server response into the internal record data structure used by RemoteStore,    
    which looks like:
      {
         item-id-string : { 
                attribute-string : [ value1,  value2 ], ...
             },
         ...
      }       
      where value is either an atomic JSON data type or 
      { 'id' : string } for references to items
      or 
      { 'type' : 'name', 'value' : 'value' } for user-defined datatypes

    _setupSaveRequest(saveKeywordArgs, requestKw)

    This function prepares the save request by populating requestKw, 
    an associative array that will be passed to dojo.io.bind.

Data Consistency Guarantees

* if two references to the same item are obtained (e.g. from two different query results) any changes to one item will be reflected in the other item reference.
* If an item has changed on the server and the item is retrieved via a new query, any previously obtained references to the item will (silently) reflect these new values.
* However, any uncommitted changes will not be "overwritten".
* If server queries are made while there are uncommitted changes, no attempt is made to evaluate whether the modifications would change the query result, e.g. add any uncommitted new items that match the query.
* However, uncomitted deleted items are removed from the query result.
* The transaction isolation level is equivalent to JDBC's "Read Committed":
  each store instance is treated as separate transaction; since there is no row or table locking so nonrepeatable and phantom reads are possible.

Memory Usage

Because Javascript doesn't support weak references or user-defined finalize methods, there is a tradeoff between data consistency and memory usage.
In order to implement the above consistency guarantees (and to provide caching), RemoteStore remembers all the queries and items retrieved. 
To reduce memory consumption, use the method forgetResults(query);

Store assumptions

RemoteStore makes some assumptions about the nature of the remote store, things may break if these aren't true:
* that the items contained in a query response include all the attributes of the item (e.g. all the columns of a row).   
  (to fix: changes need to record add and removes and fix This._data[key] = [ attributeDict, refCount]; )
* the query result may contain references to items that are not available to the client; use isItem() to test for the presence of the item.
* that modification to an item's attributes won't change it's primary key.

*/

/*
dojo.data API issues to resolve:
* save should returns a Deferred, might want to add keyword argument with 'sync' 
* clarify get/getValues() return undefined if attribute is present but has no values  
* remove hasAttributeValue()? 
 * signature of errBack, (& use for timeout?)
 * rename isItem(), to isItemAvailable() ?
 * isDirty() with no args returns whether the current transaction is dirty?
*/

dojo.lang.declare("rhizome.data.RemoteStore", [dojo.data.Read, dojo.data.Write], {

      _datatypeMap : {
          //map datatype strings to constructor function
        },

       //set to customize json serialization
       _jsonRegistry : dojo.json.jsonRegistry,

        initializer : function(kwArgs) {
            if (!kwArgs) kwArgs = {};
            this._serverQueryUrl = kwArgs.queryUrl;
            this._serverSaveUrl = kwArgs.saveUrl;
                    
           this._deleted = {}; //  //deleted items { id : 1 }    
           this._changed = {}; //{ id : { attr: [new values] } } //[] if attribute is removed
           this._added = {}; //{id : 1 } list of added items
           
           this._results = {}; //{ query : [ id1, ]};  //todo: make MRUDict of queries
            /* data is a dictionary that conforms to this format: 
              { id-string : { attribute-string : [ value1,  value2 ] } }       
              where value is either an atomic JSON data type or 
              { 'id' : string } for references to items
              or 
              { 'type' : 'name', 'value' : 'value' } for user-defined datatypes
            */ 
           this._data = {}; // { id : [values, refcount] } //todo: handle refcount
           this._numItems = 0;
        },
       
     getValues:
	 function(/* item */ item, /* attribute or attribute-name-string */ attribute) {	            
		    var id = this.isItem(item);
		    if (!id) 
		        return undefined; //todo: raise exception
		    var changes = this._changed[id];
		    if (changes) {
		        var newvalues = changes[attribute]; 
		        if (newvalues !== undefined) {
		            if (newvalues.length == 0) //attribute has been deleted
		                return undefined;
		            return  newvalues;
		        }
		   }
		  //return item.atts[attribute];
		  return this._data[id][0][attribute];
        },

	get :
		function(/* item */ item, /* attribute or attribute-name-string */ attribute,
		     /* value (optional) */ defaultValue) {
		    var valueArray = this.getValues(item, attribute);
		    if (valueArray === undefined)
		        return defaultValue;
		    return valueArray[0];
		},

    containsValue :
        function(/* item */ item, /* attribute or string */ attribute, /*value*/ value) {
              var valueArray = this.getValues(item, attribute);              
              if (valueArray) {
                for (var i=0; i < valueArray.length; i++) {                    
                    if (valueArray[i] == value) {                                
                        return true;
                    }
                }
             }
            return false;
          },
        
	hasAttribute :
		function(/* item */ item, /* attribute or attribute-name-string */ attribute) {
		    var valueArray = this.getValues(item, attribute);
		    return valueArray ? true : false;
		},

    getAttributes : function (item) {           
	    var id = this.isItem(item);
        if (!id) 
		    return undefined; //todo: raise exception

            var atts = [];
            //var attrDict = item.attrs;
            var attrDict = this._data[id][0];
            for (att in attrDict) {
                atts.push(att);
            }         
            return atts;   
        },
    
	isItem :
		function(/* anything */ something) {
		    if (!something) return false;
		    var id = something.id ? something.id : something; 
		    if (!id) return false;
		    if (this._deleted[id]) return false; //todo: do this?
		    if (this._data[id]) return  id; 
		    if (this._added[id]) return id;
		    return false;
		},

/*
	getIdentity:
		function(item) {
		    return item.id ? item.id : item;
		},


	getByIdentity:
		function(id) {		        
			var item = this._latestData[id];
			var idQuery = "/*[.='"+id+"']";
			//if (!item) item = this.find(idQuery, {async=0}); //todo: support bind(async=0)
			if (item)
			    return new _Item(id, item, this); 
		       return null;
		}
*/

        _setupQueryRequest :
            function(query, queryKwArgs, requestKw) { 
                /*
                This function prepares the query request by populating requestKw, 
                an associative array that will be passed to dojo.io.bind.
                */
                  requestKw.url =  this._serverQueryUrl + encodeURIComponent(query);
                  requestKw.method  = 'get';
                  requestKw.mimetype = "text/json";                           
             },

        _resultToQueryMetadata : function(data) { return data; } ,
        
        _resultToQueryData :
                function(data) {
                     //convert the response data into the internal data structure (see above)
                    //this implementation assumes json that looks like {  data : { ... }, format : 'format identifier', other metadata }
                    return data.data;
                },

        _remoteToLocalValues :
            function(attributes) {                
                //return attributes; //modified in-place
                for (var key in attributes) {
                     var values = attributes[key];
                     //alert( values + ' ' + typeof values);
                     for (var i = 0; i < values.length; i++) {
                        var value = values[i];                       
                        var type = value.datatype || value.type;
                        if (type) {  
                            //todo: better error handling?                            
                            var localValue = value.value;
                            if (this._datatypeMap[type]) 
                                localValue = this._datatypeMap[type](value);                            
                            values[i] = localValue;
                        }
                    }
                }
                return attributes; //modified in-place
            },

        _queryToQueryKey :
            function(query) {
                /*
                Convert the query to a string that uniquely represents this query. 
                (Used by the query cache.)
                */
                if (typeof query == "string")
                    return query;
                else
                    return dojo.json.serialize(query);                     
            },

	find :
		function(query,  keywordArgs ) {
		     /*
		     The optional keywordArgs parameter may contain:

sync : boolean, specifies whether the find operation is asynchronous or not [default if omitted: true]
onnext: callback called as each item in the result is received. Callback should expect an argument containing the item
oncompleted: callback func called, no argument (or maybe pass the result return value?)
onerror : error callback that expect an Error argument
saveResult : boolean If this is true an array (or maybe an Iterator?) will be set in the result attribute.
[default if omitted: if onnext is set, false, otherwise true]		     
		     */
		      keywordArgs = keywordArgs || {};
		     //todo: use this._results to implement caching
		     var result = new dojo.data.Result(query, this, keywordArgs);
		     var This = this;		     
             var bindfunc = function(type, data, evt) {
                    var scope= result.scope||dj_global;
                    if(type == "load"){        
                        //dojo.debug(   "loaded" + dojo.json.serialize(data)   );
                        result.resultMetadata = This._resultToQueryMetadata(data);
                        var dataDict = This._resultToQueryData(data); 
                        if (result.onbegin) {
                            result.onbegin.call(scope, result);
                        }
                        var count = 0;
                        var resultData = []; 
                        var newItemCount = 0;
                        for (var key in dataDict) {  
                            if (result._aborted) 
                                break;                                   
                            if (!This._deleted[key]) { //skip deleted items
                                //todo if in _added, remove from _added
                                var values = dataDict[key];                                        
                                var attributeDict = This._remoteToLocalValues(values);
                                var existingValue = This._data[key];
                                var refCount = 1;
                                if (existingValue)                                             
                                    refCount = ++existingValue[1]; //increment ref count                                       
                               else
                                    newItemCount++;
                               //note: if the item already exists, we replace the item with latest set of attributes
                               //this assumes queries always return complete records
                               This._data[key] = [ attributeDict, refCount]; 
                                resultData.push(key);
                                count++; 
                                if (result.onnext)
                                    result.onnext.call(scope, key, result);
                            }                                    
                        }
                        This._results[This._queryToQueryKey(query)]  = resultData; 
                        This._numItems += newItemCount;

                        result._length = count;
                        if (result.saveResult)
                            result.result = resultData;
                        if (!result._aborted && result.oncompleted) {
                            result.oncompleted.call(scope, result);
                        }                                
                    }else if(type == "error" || type == 'timeout'){
                       // here, "data" is our error object
                       //todo: how to handle timeout?
                       dojo.debug(   "error" + dojo.json.serialize(data)   );
                       if (result.onerror) 
                            result.onerror,call(scope, data);
                    }
                 }

                bindKw = keywordArgs.bindArgs || {};
                bindKw.sync = result.sync;
                bindKw.handle = bindfunc;

                this._setupQueryRequest(query, keywordArgs, bindKw);
                var request = dojo.io.bind(bindKw);
                //todo: error if not bind success
                //dojo.debug( "bind success " + request.bindSuccess);
                result._abortFunc = request.abort;     
		    return result; 
		},

/****
Write API
***/
	newItem:
		function(/* keyword arguments (optional) */ keywordArgs) {
		        //assert(typeof keywordArgs == "string"); //todo: use keyword?
		        var id = keywordArgs;
		        if (this._deleted[id]) 
		            delete this._deleted[id];		    		        
		        else {
		            this._added[id] =  1;
		            //todo? this._numItems++; ?? but its not in this._data
		        }
			return { id : id };
		},
		
	deleteItem:
		function(/* item */ item) {
		    var item= this.isItem(item);
		    if (!item) 
		        return false; 
		    
		    if (this._added[item]) 
		        delete this._added[item];
		    else {
		        this._deleted[item] = 1; 
		        //todo? this._numItems--; ?? but its still in this._data
		    }
		        
		    if (this._changed[item]) 
		        delete this._changed[item];		    
	            return true; 
		},
		
	setValues:
		function(/* item */ item, /* attribute or string */ attribute, /* array */ values) {
		    var item = this.isItem(item);
		    if (!item) 
		        return undefined; //todo: raise exception

		    var changes = this._changed[item];
		    if (!changes) {
		        changes = {}
		        this._changed[item] = changes;
		    } 		    		
		    changes[attribute] = values;
	            return true; // boolean
		},

	set:
		function(/* item */ item, /* attribute or string */ attribute, /* almost anything */ value) {
			return this.setValues(item, attribute, [value]); 
		},

	unsetAttribute :
		function(/* item */ item, /* attribute or string */ attribute) {
			return this.setValues(item, attribute, []); 
		},

   _initChanges :
              function() {
                   this._deleted = {}; 
                   this._changed = {};
                   this._added = {}; 
             },

        _setupSaveRequest :
            function(saveKeywordArgs, requestKw) { 
                 /*
                 This function prepares the save request by populating requestKw, 
                 an associative array that will be passed to dojo.io.bind.
                 */
                  requestKw.url =  this._serverSaveUrl;
                  requestKw.method  = 'post';
                  requestKw.mimetype = "text/plain";   
                  var deleted  = [];
                  for (var key in this._deleted) {
                      deleted.push(key);
                  }
                  //don't need _added in saveStruct, changed covers that info                  
                  saveStruct = { 'changed' : this._changed, 'deleted' : deleted };
                  var oldRegistry = dojo.json.jsonRegistry;
                  dojo.json.jsonRegistry = this._jsonRegistry;
                  var jsonString = dojo.json.serialize(saveStruct);
                  dojo.json.jsonRegistry = oldRegistry;
                  requestKw.postContent =  jsonString;
          },

         save :
		function(keywordArgs) {
		    /*
		    The optional keywordArgs parameter may contain 'sync' to specify 
		    whether the save operation is asynchronous or not (the default is asynchronous).
		    */
		     keywordArgs = keywordArgs || {};
		     var result = new dojo.Deferred();		     
		     var This = this;
		     		     
                     var bindfunc = function(type, data, evt) {                        
                        
                         if(type == "load"){ 
                            if (result.fired == 1) {
                                //it seems that mysteriously "load" sometime gets called after "error"
                                //so check if an error has already occurred and stop if it has 
                                return;
                            }
        		    //update this._data upon save
        		    var key = null;
    		            for (key in This._added) {
    		              if (!This._data[key])
    		                This._data[key] = [{} , 1];
    		            }
    		           for (key in This._changed) {
    		              var existing = This._data[key];
    		              var changes = This._changed[key];
    		               if (existing)
    		                   existing[0] = changes;
    		               else
    		                  This._data[key] = [changes, 1];
    		           }
    		           for (key in This._deleted) {
    		              if (This._data[key])
    		                delete This._data[key];
    		           }
    		           This._initChanges(); 
                           result.callback(true); //todo: what result to pass?
                       } else if(type == "error" || type == 'timeout'){
                             result.errback(data); //todo: how to handle timeout
                       }
                       
                    }
                    
                    bindKw = { sync : keywordArgs["sync"], 
                                      handle: bindfunc };
                    this._setupSaveRequest(keywordArgs, bindKw);
                    var request = dojo.io.bind(bindKw);
                    result.canceller = function(deferred) { request.abort(); };
                    
		    return result; 
		},
             
	revert:
		function() {
                   this._initChanges(); 
	           return true;
		},

	isDirty:
		function(/* item (or store) */ item) {
		    if (item) {
		         item = item.id || item;
                         return this._deleted[item] || this._changed[item];
		    } else {
		        var key = null;
		        for (key in this._changed) 
		              return true;		        
		        for (key in this._deleted) 
		              return true;
		        for (key in this._added) 
		              return true;

		        return false;
		    }
	      },

/**
   additional public methods
*/
            createReference : function(idstring) {
                return { id : idstring };
            },

            getSize : function() { return this._numItems; },
            
            forgetResults :
              function(query) {
                  var queryKey = this._queryToQueryKey(query);
                  var results = this._results[queryKey];
                  if (!results) return false;

                  var removed = 0;
                  for (var i = 0; i < results.length; i++) {
                        var key = results[i];
                        var existingValue = this._data[key];
                        if (existingValue[1] <= 1) {
                            delete this._data[key];
                            removed++;
                        }
                        else
                            existingValue[1] = --existingValue[1];                        
                  }
                  delete this._results[queryKey];                
                  this._numItems -= removed;
                  return true;
              } 
});



