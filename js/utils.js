// Simple JavaScript Templating
// John Resig - http://ejohn.org/ - MIT Licensed
(function(){
  var cache = {};
 
  this.tmpl = function tmpl(str, data){
    // Figure out if we're getting a template, or if we need to
    // load the template - and be sure to cache the result.
    var fn = !/\W/.test(str) ?
      cache[str] = cache[str] ||
        tmpl(document.getElementById(str).innerHTML) :
     
      // Generate a reusable function that will serve as a template
      // generator (and which will be cached).
      new Function("obj",
        "var p=[],print=function(){p.push.apply(p,arguments);};" +
       
        // Introduce the data as local variables using with(){}
        "with(obj){p.push('" +
       
        // Convert the template into pure JavaScript
        str
          .replace(/[\r\t\n]/g, " ")
          .split("<%").join("\t")
          .replace(/((^|%>)[^\t]*)'/g, "$1\r")
          .replace(/\t=(.*?)%>/g, "',$1,'")
          .split("\t").join("');")
          .split("%>").join("p.push('")
          .split("\r").join("\\'")
      + "');}return p.join('');");
   
    // Provide some basic currying to the user
    return data ? fn( data ) : fn;
  };
})();

(function($){
  $.timeago = function(timestamp){
    if(timestamp instanceof Date) return inWords(timestamp);
    else if(typeof timestamp=="string") return inWords($.timeago.parse(timestamp));
    else return inWords($.timeago.parse($(timestamp).attr("datetime")));
  };
  var $t = $.timeago;
  $.extend(
    $.timeago,
    {
      settings: {
        refreshMillis: 60000,
        allowFuture: false,
        strings: {
          ago: "ago",
          fromNow: "from now",
          seconds: "less than a minute",
          minute: "about a minute",
          minutes: "%d minutes",
          hour: "about an hour",
          hours: "about %d hours",
          day: "a day",
          days: "%d days",
          month: "about a month",
          months: "%d months",
          year: "about a year",
          years: "%d years"
        }
      },
      inWords: function(distanceMillis){
        var $l = this.settings.strings;
        var suffix = $l.ago;
        if (this.settings.allowFuture){
          if(distanceMillis < 0) suffix = $l.fromNow;
          distanceMillis = Math.abs(distanceMillis);
        }
        var seconds = distanceMillis/1000;
        var minutes = seconds/60;
        var hours = minutes/60;
        var days = hours/24;
        var years = days/365;
        var words =
          seconds < 45 && sprintf($l.seconds,Math.round(seconds)) ||
          seconds < 90 && $l.minute ||
          minutes < 45 && sprintf($l.minutes,Math.round(minutes)) ||
          minutes < 90 && $l.hour ||
          hours < 24 && sprintf($l.hours,Math.round(hours)) ||
          hours < 48 && $l.day ||
          days < 30 && sprintf($l.days,Math.floor(days)) ||
          days < 60 && $l.month ||
          days < 365 && sprintf($l.months,Math.floor(days/30)) ||
          years < 2 && $l.year ||
          sprintf($l.years,Math.floor(years));
        return words + " " + suffix;
      },
      parse: function(iso8601){
        var s = $.trim(iso8601);
        s = s.replace(/-/,"/").replace(/-/,"/");
        s = s.replace(/T/," ").replace(/Z/," UTC");
        s = s.replace(/([\+-]\d\d)\:?(\d\d)/," $1$2");
        return new Date(s);
      }
    }
  );
  $.fn.timeago = function(){
    var self = this;
    self.each(refresh);
    var $s = $t.settings;
    if ($s.refreshMillis > 0){
      setInterval(function(){ self.each(refresh); }, $s.refreshMillis);
    }
    return self;
  };
  function refresh(){
    var date = $t.parse($(this).attr("datetime"));
    if (!isNaN(date)){
      $(this).text(inWords(date));
    }
    return this;
  }
  function inWords(date){return $t.inWords(distance(date));}
  function distance(date){return(new Date().getTime()-date.getTime());}
  function sprintf(string,value){return string.replace(/%d/i,value);}
})(jQuery);
