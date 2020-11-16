function getURLParams(paramKey) {
    const params = new URLSearchParams(document.location.search);
    var s = params.get(paramKey);
    return s;
}

function getImageURL() {
    var fragmentNumber = getURLParams('fragmentNumber');
    var url = "https://owner-photos.s3.amazonaws.com/" + fragmentNumber + ".jpg";
    return url;
}

function submit() 
{
    var fragmentNumber = getURLParams('fragmentNumber');
    var name = document.getElementById("name").value;
    var number = document.getElementById("number").value;
    var apigClient = apigClientFactory.newClient();
    var msg = "Could not update the visitor information";
	let params = {};
	var body = {
        "fragmentNumber": fragmentNumber,
        "name" : name,
        "number" : number
    };
	console.log("Body content are");
    console.log(body);
    apigClient.rootPost(params,body)
	.then(function(result){
		console.log("result content are");
		console.log(result);
        msg = result['data']['body'];
        console.log("Message is" + msg);
        document.getElementById("response").innerHTML = '<h4 style="color:green">' + msg + '</h4>';
	}).catch(function(result) {
        console.log("ERROR: " + result);
        document.getElementById("response").innerHTML = msg;
    });
}