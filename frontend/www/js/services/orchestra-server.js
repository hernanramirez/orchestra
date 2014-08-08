(function(){

'use strict';

angular.module('OrchestraServer', [])

.factory('orchestraServer', ['$http', '$q', function($http, $q) {
    
    
    var svc = {};
    svc.baseUrl = "http://localhost:8000/"

    var simpleGet = function(url){
        var deferred = $q.defer();
        var url = svc.baseUrl + url;
        $http.get(url).then(function(resp){
            deferred.resolve(resp.data);
            console.log("x", resp.data)
        });
        return deferred.promise;
    };

    var simpleGetDrfList = function(url){
        var deferred = $q.defer();
        var url = svc.baseUrl + url;
        $http.get(url).then(function(resp){
            deferred.resolve(resp.data.results);
            console.log("x", resp.data.results)
        });
        return deferred.promise;
    };

   


    svc.getMetaWorkflows = function(){
        return simpleGet("api/metaworkflows/")
    };


    svc.getMetaWorkflow = function(name){
        return simpleGet("api/metaworkflows/" + name + "/")
    };

    svc.getWorkflows = function(){
        return simpleGetDrfList("api/workflows/")
    };

    svc.getWorkflow = function(id){
        return simpleGet("api/workflows/" + id + "/")
    };

    svc.createWorkflow = function(name){
        var url = svc.baseUrl + 'api/wf/create/'
        return $http.post(url, { name:name});

    }


    return svc;





}]);






})();