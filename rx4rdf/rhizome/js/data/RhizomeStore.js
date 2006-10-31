dojo.provide("rhizome.data.RhizomeStore");
dojo.require("dojo.lang.declare");
dojo.require("rhizome.data.RemoteStore");

function DatatypeSerializer(type, convert, uri) {
    this.type = type;
    this._converter =  convert;
    this.uri = uri;
    this.serialize = function(value) { return this._converter.call(value, value); }     
}

dojo.declare("rhizome.data.RhizomeStore", rhizome.data.RemoteStore, {

      _datatypeMap : {
          //map datatype strings to constructor function
          literal : function(value) { 
            var literal = value.value;  
            if (value["xml:lang"]) {
                literal.lang = value["xml:lang"];
            }
            return literal;
        },
        
        uri : function(value) { return { id : value.value  }; },
         
        bnode  : function(value) { return { id : '_:' + value.value  }; }

        ,'http://www.w3.org/2001/XMLSchema#int' : function(value) { return parseInt(value.value); }
        ,'http://www.w3.org/2001/XMLSchema#integer' : function(value) { return parseInt(value.value); }
        ,'http://www.w3.org/2001/XMLSchema#long' : function(value) { return parseInt(value.value); }
        
        ,'http://www.w3.org/2001/XMLSchema#float' : function(value) { return parseFloat(value.value); }
        ,'http://www.w3.org/2001/XMLSchema#double' : function(value) { return parseFloat(value.value); }

        ,'http://www.w3.org/2001/XMLSchema#boolean' : function(value) { return !value || value == "false" || value == "0" ? false : true; }

        //todo: more datatypes: 
        //integer subtypes, string types, XMLiteral
        //,'http://www.w3.org/2001/XMLSchema#... : function(value) { return parseInt(value.value); }
        },

       datatypeSerializers : [
           new DatatypeSerializer(Number, Number.toString, 'http://www.w3.org/2001/XMLSchema#float')
           ,new DatatypeSerializer(Boolean, Boolean.toString, 'http://www.w3.org/2001/XMLSchema#boolean')
      ],

        initializer : function(kwArgs) {            
            this._serverQueryUrl = kwArgs.baseUrl + 'search?view=json&searchType=RxPath&search=';
            this._serverSaveUrl = kwArgs.baseUrl + 'save-metadata';
       },      
       
       findDatatype : function(value) {          
           var length = this.datatypeSerializers.length;            
            for (var i = 0; i < length; i++) {
                var datatype = this.datatypeSerializers[i];
                if (value instanceof datatype.type) {
                    return datatype;
                } 
           } 
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
                                    
                  var resources = [];                                                                       
                  for (var key in this._deleted) {
                      resources.push(key);                  
                  }

                  var changes = {};
                  for (var key in this._changed) {
                      if (!this._added[key])  {//don't put new resources in this list
                        resources.push(key);                  
                     }
                     
                     var attributes = this._changed[key];
                     var rdfattributes = {};
                     for (var attr in attributes) {                            
                            var values = attributes[attr];
                            if (!values.length) continue;
                            var rdfvalues = [];
                            //convert values to rdf json format
                            //(from http://www.w3.org/TR/2006/NOTE-rdf-sparql-json-res-20061004/)
                            for (var i = 0; i < values.length; i++) {                                
                                var value = values[i];                       
                                var rdfvalue = {};
                                if (value.id) {                                    
                                    if (value.id.slice(0, 2) == '_:') {
                                         rdfvalue.type = 'bnode';
                                         rdfvalue.value = value.id.substring(2);
                                   } else {
                                         rdfvalue.type = 'uri';
                                         rdfvalue.value = value.id;  
                                  }
                                }
                                else if (typeof value == "string" || value instanceof String) {
                                         rdfvalue.type = 'literal';
                                         rdfvalue.value = value;
                                         if (value.lang) 
                                            rdfvalue["xml:lang"] = value.lang;
                                }
                                else {
                                    if (typeof value == "number")
                                        value = new Number(value);
                                    else if (typeof value == "boolean")
                                        value = new Boolean(value);
                                        
                                    var datatype = this.findDatatype(value);
                                    if (datatype) {
                                        rdfvalue = {"type":"typed-literal", 
                                            "datatype": datatype.uri,  "value": value.toString()
                                                //todo: datatype.serialize(value) causes
                                                //Error: Function.prototype.toString called on incompatible number
                                                };
                                    }
                                    else {
                                        //treat it as a string 
                                        //todo: warn?
                                        rdfvalue = { "type":"literal", "value": value.toString() };
                                    }
                                    rdfvalues.push( rdfvalue) ;
                                }                                
                          }
                          rdfattributes[attr] = rdfvalues;
                      }
                     changes[key] = rdfattributes;
                  }
                                    
                  var oldRegistry = dojo.json.jsonRegistry;
                  dojo.json.jsonRegistry = this._jsonRegistry;
                  var jsonString = dojo.json.serialize(changes);
                  dojo.json.jsonRegistry = oldRegistry;

                  requestKw.content = { rdfFormat : 'json' , 
                    resource :  resources, 
                   metadata :  jsonString
                 };
          },
        
        _resultToQueryData :
                function(json) { return json; }
});

