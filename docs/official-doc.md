<!-- OFFICIAL Warframe Market API v2 documentation — server v0.23.0.
Rendered verbatim from the official Notion doc via web/scripts/extract-notion.mjs:
https://42bytes.notion.site/WFM-Api-v2-Documentation-5d987e4aa2f74b55a80db1a09932459d
Kept as the long original reference. For voidbroker's internal notes / what we actually
use + live-verified corrections, see wfm-api.md. -->

General
Version
Base URLs
Rate limits
Global Parameters
Language Header
Platform Header
Crossplay Header
Response Structure
Errors
Hitting rate limits or other protection from CF
Handled errors
Unhandled errors
Endpoints
Manifests
GET /v2/versions
GET /v2/items 
GET /v2/item/{slug} 
GET /v2/item/{slug}/set 
GET /v2/riven/weapons 
GET /v2/riven/weapon/{slug} 
GET /v2/riven/attributes 
GET /v2/lich/weapons 
GET /v2/lich/weapon/{slug} 
GET /v2/lich/ephemeras 
GET /v2/lich/quirks 
GET /v2/sister/weapons 
GET /v2/sister/weapon/{slug} 
GET /v2/sister/ephemeras 
GET /v2/sister/quirks 
GET /v2/locations 
GET /v2/npcs 
GET /v2/missions 
Orders
GET /v2/orders/recent 
GET /v2/orders/item/{slug} 
GET /v2/orders/item/{slug}/top 
GET /v2/orders/user/{slug}
GET /v2/orders/my 
GET /v2/order/{id}
POST /v2/order 
PATCH /v2/order/{id} 
DELETE /v2/order/{id} 
POST /v2/order/{id}/close 
PATCH /v2/orders/group/{id} 
Groups
Users
GET /v2/me 
PATCH /v2/me 
POST /v2/me/avatar 
POST /v2/me/background 
GET /v2/user/{slug}
Achievements
GET /v2/achievements 
GET /v2/achievements/user/{slug} 
Authentication
POST /auth/signin 
POST /auth/signup 
POST /auth/refresh
POST /auth/signout 
Dashboard
GET /v2/dashboard/showcase 
OAuth
General
Check other related documentation as well:
Data Models
Websockets
OAuth 2.0
Version
Documentation describes: v0.23.0
Base URLs
Api base path: https://api.warframe.market/v2/
Some fields could be a path to item icon, or user avatar, or profile background, like: items/images/en/dual_rounds.304395bed5a40d76ddb9a62c76736d94.png
base path for all kind of these things is: https://warframe.market/static/assets/
Rate limits
3 requests per second, for now, probably i’ll rise it later.
Global Parameters
For each query, you can or must add these parameters to get the results you are looking for.
Language Header
WFM supports 14 languages:
ko, ru, de, fr, pt, zh-hans, zh-hant, es, it, pl, uk, tr, ja, en
For response data that includes an i18n field, WFM can provide translations in addition to the default English (en) translation. 
To request a translation in one of the supported languages, include the Language: {lang} header in your API request, where {lang} is the code of the desired language.
Default value is en
Example:
Send request with Language: ko 
Get response like:
{
	i18n: {
		en: {...},
		ko: {...}
	}
}

​
Platform Header
WFM is designed to cater to users across various gaming platforms. It currently supports five platforms: pc, ps4, xbox, switch, mobile
To access content specific to a particular platform, it is necessary to include the Platform: {platform} header in your API request. In this header, {platform} should be replaced with the code corresponding to the desired platform.
Default value is pc
Crossplay Header
In addition to platforms, we also have cross-play option.
Players across different platforms can trade if they have cross-play enabled in their game settings.
Here’s how the headers work.
Let’s say you want to retrieve all orders from PC and also include cross-play orders from other platforms. In this case, you can set the headers like this:
Platform: pc
Crossplay: true
​
On the other hand, if you only want to get orders from PC and exclude cross-play orders from other platforms, use:
Platform: pc
Crossplay: false
 You will still receive orders or contracts from players who have PC and cross-play enabled.
​
Default value is false
Response Structure
Response body:
{
	"apiVersion": "x.x.x",
	"data": {},
	"error": null
}

​
Where:
apiVersion string - semVer-compatible API server version.
data object or array or null - response payload for successful requests.
error object or null - error payload for handled errors.
Errors
Hitting rate limits or other protection from CF
WFM implements rate limits to ensure fair usage and protect against excessive requests per second (RPS).
Exceeding these limits results in a 429 error code, often accompanied by a CloudFlare challenge page. In some cases, excessive RPS may lead to outright blocking by CloudFlare.
Additionally, if there are too many concurrent connections from a single IP address, a 509 error code is returned.
This is a measure to prevent overloading the server with multiple connections from the same source.
Handled errors
{
  apiVersion: "x.x.x",
	data: null,
	error: {
		request: [...],
		inputs: {
		    fieldOne: "",
		    fieldTwo: "",
		    ...
		},
	},
}

​
Where:
request []string - general level request error, like app.errors.unauthorized, app.errors.forbidden, app.order.error.exceededOrderLimit, etc
inputs map[string]string - input level errors, like form errors, query param errors, multipart/form-data errors.
Example, you are trying to create an order, and put platinum as -1, you will get:
inputs: {platinum: “app.field.tooSmall”}
Unhandled errors
Request killed goroutine for some reason, critical error.
You will get 5xx error without any content.
Endpoints
Authorization Tokens obtained from v1 Api by default have scope: all
This means, if you are using v1 auth, you can ignore scope requirements, for now.
But, eventually v1 login endpoint would be removed in favor of OAuth2.0 system.
Here is our advanced endpoint marking system:
 - In development
 - Unstable or unfinished endpoints, use at your own risk
 - Rate limited endpoints, mind you calls lads
 - Require authorization
 - Available only for 1st party apps
 - Content depends on defined platform and crossplay headers
 - Can request additional translations
 - Deprecated
Manifests
Sounds familiar …
GET  /v2/versions 
This endpoint retrieves the current version number of the server's resources, formatted either as a semVer string or as an arbitrary version identifier.
Whenever the server database is updated or new versions of mobile apps are released, the version number for relevant resources is also updated.
Client applications can check this endpoint periodically to fetch the current server version. A discrepancy between the server's version number and the client's indicates that an update has occurred. In such cases, clients should refresh their local data, like re-downloading item lists, to stay synchronized with the server's latest updates.
URL parameters:
None
Response:
{
	"apiVersion": "x.x.x",
	"data": {
		"apps": {
			"ios": "x.x.x",
			"android": "x.x.x",
			"minIos": "x.x.x",
			"minAndroid": "x.x.x"
		},
		"collections": {
			"items": "base64",
			"rivens": "base64",
			"liches": "base64",
			"sisters": "base64",
			"missions": "base64",
			"npcs": "base64",
			"locations": "base64"
		},
		"updatedAt": "2021-05-21T14:59:02Z"
	},
	"error": null
}

​
GET  /v2/items ​
Get list of all tradable items
URL parameters:
None
Response:
{
apiVersion: "x.x.x",
data: [
	ItemShort,
	ItemShort,
	...
],
error: null
}

Data model inside: ItemShort
​
GET  /v2/item/{slug} ​
GET  /v2/itemId/{itemId}
Get full info about one, particular item
URL parameters:
 slug - slug field form Item and ItemShort models
 itemId - id field form Item and ItemShort models
Response:
{
apiVersion: "x.x.x",
data: Item,
error: null
}

Data model inside: Item
​
GET  /v2/item/{slug}/set ​
GET  /v2/itemId/{itemId}/set
Retrieve Information on Item Sets
In WFM, items can either be standalone or part of a set. A set is a collection of related items that are often traded together.
If the queried item is not part of any set, the response will contain an array with just that one item.
If the item is part of a set or is a set itself, the response will include an array of all items within that set. 
URL parameters:
 slug - slug field form Item and ItemShort models
 itemId - id field form Item and ItemShort models
Response:
{
	"apiVersion": "x.x.x",
	"data": {
		"id": "54a73e65e779893a797fff72",
		"items": [
			Item,
			Item,
			...
		]
	},
	"error": null
}

Data model inside: Item
​
Response Fields
Field
	
Type
	
Description


id
	
string
	
Id of the requested item.


items
	
Item[]
	
Items in the set, or only the requested item when it is not part of a set.
GET  /v2/riven/weapons ​
Get list of all tradable riven items
URL parameters:
None
Response:
{
apiVersion: "x.x.x",
data: [
	Riven,
	Riven,
	...
],
error: null
}

Data model inside is clickable: Riven
​
GET  /v2/riven/weapon/{slug} ​
Get full info about one, particular riven item
URL parameters:
 slug - field form Riven model
Response:
{
apiVersion: "x.x.x",
data: Riven,
error: null
}

Data model inside: Riven
​
GET  /v2/riven/attributes ​
Get list of all attributes for riven weapons
URL parameters:
None
Response:
{
apiVersion: "x.x.x",
data: [
	RivenAttribute,
	RivenAttribute,
	...
],
error: null
}

Data model inside: RivenAttribute
​
GET  /v2/lich/weapons ​
Get list of all tradable lich weapons
URL parameters:
None
Response:
{
apiVersion: "x.x.x",
data: [
	LichWeapon,
	LichWeapon,
	...
],
error: null
}

Data model inside: LichWeapon
​
GET  /v2/lich/weapon/{slug} ​
Get full info about one, particular lich weapon
URL parameters:
 slug - field form LichWeapon model
Response:
{
apiVersion: "x.x.x",
data: LichWeapon,
error: null
}

Data model inside: LichWeapon
​
GET  /v2/lich/ephemeras ​
Get list of all tradable lich ephemeras
URL parameters:
None
Response:
{
apiVersion: "x.x.x",
data: [
	LichEphemera,
	LichEphemera,
	...
],
error: null
}

Data model inside: LichEphemera
​
GET  /v2/lich/quirks ​
Get list of all tradable lich quirks
URL parameters:
None
Response:
{
apiVersion: "x.x.x",
data: [
	LichQuirk,
	LichQuirk,
	...
],
error: null
}

Data model inside: LichQuirk
​
GET  /v2/sister/weapons ​
Get list of all tradable sister weapons
URL parameters:
None
Response:
{
apiVersion: "x.x.x",
data: [
	SisterWeapon,
	SisterWeapon,
	...
],
error: null
}

Data model inside: SisterWeapon
​
GET  /v2/sister/weapon/{slug} ​
Get full info about one, particular sister weapon
URL parameters:
 slug - field form SisterWeapon model
Response:
{
apiVersion: "x.x.x",
data: SisterWeapon,
error: null
}

Data model inside: SisterWeapon
​
GET  /v2/sister/ephemeras ​
Get list of all tradable sister ephemera’s
URL parameters:
None
Response:
{
apiVersion: "x.x.x",
data: [
	SisterEphemera,
	SisterEphemera,
	...
],
error: null
}

Data model inside: SisterEphemera
​
GET  /v2/sister/quirks ​
Get list of all tradable sister quirks
URL parameters:
None
Response:
{
apiVersion: "x.x.x",
data: [
	SisterQuirk,
	SisterQuirk,
	...
],
error: null
}

Data model inside: SisterQuirk
​
GET  /v2/locations ​
Get list of all locations (that are known to WFM)
URL parameters:
None
Response:
{
apiVersion: "x.x.x",
data: [
	Location,
	Location,
	...
],
error: null
}

Data model inside: Location
​
GET  /v2/npcs ​
Get list of all NPC’s (that are known to WFM)
URL parameters:
None
Response:
{
apiVersion: "x.x.x",
data: [
	Npc,
	Npc,
	...
],
error: null
}

Data model inside: Npc
​
GET  /v2/missions ​
Get list of all Missions (that are known to WFM)
URL parameters:
None
Response:
{
apiVersion: "x.x.x",
data: [
	Mission,
	Mission,
	...
],
error: null
}

Data model inside: Mission
​
Orders
GET  /v2/orders/recent ​
Get the most recent visible orders from non-banned users.
Returns up to 500 orders created in the last 4h, sorted by createdAt descending. Results depend on the Platform and Crossplay headers, include only users currently online, and are cached with a 1m refresh interval.
URL parameters:
None
Response:
{
	"apiVersion": "x.x.x",
	"data": [
		Order,
		Order,
		...
	],
	"error": null
}

Data model inside: OrderWithUser
​
GET  /v2/orders/item/{slug} ​
GET  /v2/orders/itemId/{itemId}
Get visible orders for an item from non-banned users whose lastSeen is within the last 48h, or whose lastSeen is missing. Results depend on the Platform and Crossplay headers. Current user status is refreshed in the response, but offline users are not removed by this endpoint.
URL parameters:
 slug - slug field from the Item or ItemShort model.
 itemId - id field from the Item or ItemShort model.
Response:
{
	"apiVersion": "x.x.x",
	"data": [
		Order,
		Order,
		...
	],
	"error": null
}

Data model inside: OrderWithUser
​
GET  /v2/orders/item/{slug}/top ​
GET  /v2/orders/itemId/{itemId}/top
Get the top buy and sell orders for an item from online users.
Results depend on the Platform and Crossplay headers. The response contains up to 5 sell orders and up to 5 buy orders.
Sell orders are ranked from the buyer's point of view: Endo listings first, then better Endo-per-platinum ratio for Endo listings, otherwise lower platinum-per-trade first. Buy orders are ranked from the seller's point of view: Endo listings first, then lower Endo-per-platinum ratio for Endo listings, otherwise higher platinum-per-trade first.
URL parameters:
 slug - slug field from the Item or ItemShort model.
 itemId - id field from the Item or ItemShort model.
Query parameters
 ▸  rank int - Exact item rank. Accepted range: 0 to item max rank. Ignored when the item has no ranks or when rankLt is provided.
 ▸  rankLt int - Match ranks lower than this value. Accepted range: 1 to item max rank. Takes precedence over rank.
 ▸  charges int - Exact remaining charges. Accepted range: 0 to item max charges. Ignored when the item has no charges or when chargesLt is provided.
 ▸  chargesLt int - Match remaining charges lower than this value. Accepted range: 1 to item max charges. Takes precedence over charges.
 ▸  amberStars int - Exact amber star count. Accepted range: 0 to item max amber stars. Ignored when the item has no amber stars or when amberStarsLt is provided.
 ▸  amberStarsLt int - Match amber star counts lower than this value. Accepted range: 1 to item max amber stars. Takes precedence over amberStars.
 ▸  cyanStars int - Exact cyan star count. Accepted range: 0 to item max cyan stars. Ignored when the item has no cyan stars or when cyanStarsLt is provided.
 ▸  cyanStarsLt int - Match cyan star counts lower than this value. Accepted range: 1 to item max cyan stars. Takes precedence over cyanStars.
 ▸  subtype string - Exact item subtype. Must be one of the subtypes supported by the item. Ignored when the item has no subtypes.
Response:
{
	"apiVersion": "x.x.x",
	"data": {
		"sell": [
			Order,
			Order,
			...
		],
		"buy": [
			Order,
			Order,
			...
		]
	},
	"error": null
}

​
Response Fields
Field
	
Type
	
Description


sell
	
Order[]
	
Up to 5 sell orders from online users, sorted from the buyer's point of view.


buy
	
Order[]
	
Up to 5 buy orders from online users, sorted from the seller's point of view.
GET  /v2/orders/user/{slug} 
GET  /v2/orders/userId/{userId}
Get public orders from the specified user. Anonymous users and unrelated users receive only visible orders. The requested user and users with role moderator and higher receive visible and hidden orders.
URL parameters:
 userId - id field from the User or UserShort model.
 slug - slug field from the User or UserShort model.
Response:
{
	"apiVersion": "x.x.x",
	"data": [
		OrderCompact,
		OrderCompact,
		...
	],
	"error": null
}

Data model inside: Order
​
GET  /v2/orders/my ​
Get all orders associated with the authenticated user, including visible and hidden orders.
URL parameters:
None
Response:
{
	"apiVersion": "x.x.x",
	"data": [
		OrderCompact,
		OrderCompact,
		...
	],
	"error": null
}

Data model inside: Order
​
GET  /v2/order/{id}
Get an order by id.
URL parameters:
 id - id field from the Order model.
Response:
{
	"apiVersion": "x.x.x",
	"data": OrderCompact,
	"error": null
}

Data model inside: OrderWithUser
​
POST  /v2/order ​
Create a new order.
Requires:
Authentication
Verified account
User must not be banned
Request body
{
	"itemId": "54aae292e7798909064f1575",
	"type": "sell",
	"platinum": 38,
	"quantity": 12,
	"visible": true,
	"perTrade": 6,
	"rank": 5,
	"charges": 3,
	"subtype": "blueprint",
	"amberStars": 3,
	"cyanStars": 3
}

​
Request Fields
Field
	
Type
	
Description


itemId
	
string
	
Item id. Item must exist and be tradable.


type
	
"sell" or "buy"
	
Order type.


platinum
	
int
	
Price in platinum. Min: 1. Max: 900000.


quantity
	
int
	
Order quantity. Min: 1. Max: 9999.


visible
	
bool
	
Whether the order is visible. Defaults to false when omitted.


perTrade
	
int
	
Required for bulk-tradable items, forbidden otherwise. Min: 1. Max: 6. Must divide quantity.


rank
	
int
	
Required when the item supports ranks, forbidden otherwise. Min: 0. Max: item max rank.


charges
	
int
	
Required when the item supports charges, forbidden otherwise. Min: 0. Max: item max charges.


subtype
	
string
	
Required when the item has subtypes, forbidden otherwise. Must be one of the item's subtypes.


amberStars
	
int
	
Required when the item supports amber stars, forbidden otherwise. Min: 0. Max: item max amber stars.


cyanStars
	
int
	
Required when the item supports cyan stars, forbidden otherwise. Min: 0. Max: item max cyan stars.
Response:
{
	"apiVersion": "x.x.x",
	"data": OrderCompact,
	"error": null
}

Data model inside: Order
​
PATCH  /v2/order/{id} ​
Patch an existing order.
Requires:
Authentication
Verified account
Order owner or role admin and higher
URL parameters:
 id - id field from the Order model.
Request body
{
	"platinum": 10,
	"quantity": 12,
	"perTrade": 3,
	"rank": 1,
	"charges": 2,
	"amberStars": 2,
	"cyanStars": 2,
	"subtype": "blueprint",
	"visible": false
}

​
Request Fields
Field
	
Type
	
Description


platinum
	
int
	
Price in platinum. Min: 1. Max: 900000.


quantity
	
int
	
Order quantity. Min: 1. Max: 9999.


visible
	
bool
	
Whether the order is visible.


perTrade
	
int
	
Allowed only for bulk-tradable items. Min: 1. Max: 6. Must divide the final quantity.


rank
	
int
	
Allowed only when the item supports ranks. Min: 0. Max: item max rank.


charges
	
int
	
Allowed only when the item supports charges. Min: 0. Max: item max charges.


subtype
	
string
	
Allowed only when the item has subtypes. Must be one of the item's subtypes.


amberStars
	
int
	
Allowed only when the item supports amber stars. Min: 0. Max: item max amber stars.


cyanStars
	
int
	
Allowed only when the item supports cyan stars. Min: 0. Max: item max cyan stars.
Response
{
	"apiVersion": "x.x.x",
	"data": OrderCompact,
	"error": null
}

Data model inside: Order
​
DELETE  /v2/order/{id} ​
Delete an order.
Requires:
Authentication
Verified account
Order owner or role admin and higher
URL parameters:
 id - id field from the Order model.
Response
{
	"apiVersion": "x.x.x",
	"data": OrderCompact,
	"error": null
}

Data model inside: Order
​
POST  /v2/order/{id}/close ​
Close a portion or all of an existing order. If quantity is greater than the remaining order quantity, the service closes the remaining quantity. Full close deletes the order; partial close updates the remaining quantity.
Requires:
Authentication
Verified account
User must not be banned
Order owner or role admin and higher
URL parameters:
 id - id field from the Order model.
Request body
{
	"quantity": 12
}

​
Request Fields
Field
	
Type
	
Description


quantity
	
int
	
Units to close. Min: 1. Max: 9999. Must be divisible by the order's perTrade.
Response:
{
	"apiVersion": "x.x.x",
	"data": TransactionCompact,
	"error": null
}

Data model inside is: Transaction, will not include User model in this case.
​
PATCH  /v2/orders/group/{id} ​
Update visibility for a virtual order group.
Requires:
Authentication
Verified account
URL parameters:
 id - Group id. Currently supported values: all, ungrouped.
Request body
{
	"visible": false,
	"type": "sell"
}

​
Request Fields
Field
	
Type
	
Description


visible
	
bool
	
Visibility state to apply. Defaults to false when omitted.


type
	
"sell" or "buy"
	
Restrict the update to one order type. Omit to update both types.
Response:
{
	"apiVersion": "x.x.x",
	"data": {
		"updated": 13
	},
	"error": null
}

​
Response Fields
Field
	
Type
	
Description


updated
	
int
	
Number of orders updated.
Groups
Endpoints to manage order and contract groups.
Currently, only two virtual groups are available for use with any endpoint that requires a groupId:
all - includes all orders \ contracts, whether grouped or ungrouped.
ungrouped - includes only orders \ contracts that are not assigned to any group.
Groups management endpoints will be published later (create, update, delete, etc)
Users
GET  /v2/me ​
Get information about the authenticated user.
Requires:
Authentication
Response:
{
	"apiVersion": "x.x.x",
	"data": UserPrivate,
	"error": null
}

​
PATCH  /v2/me ​
Update the authenticated user's profile preferences.
Requires:
Authentication
Request body
{
	"about": "something",
	"platform": "mobile",
	"crossplay": true,
	"locale": "pt",
	"theme": "light",
	"syncLocale": true,
	"syncTheme": true
}

​
Request Fields
Field
	
Type
	
Description


about
	
string
	
Profile description in Markdown. Max: 300 characters. Returned as about HTML and aboutRaw Markdown.


platform
	
Platform
	
Main platform the user plays on.


crossplay
	
bool
	
Whether crossplay is enabled for the user's Warframe account. Cannot be true when the effective platform is switch.


locale
	
Language
	
UI locale and preferred communication language.


theme
	
"light" or "dark" or "system"
	
UI theme preference.


syncLocale
	
bool
	
Whether locale should sync across devices.


syncTheme
	
bool
	
Whether theme should sync across devices.
Constraints
Omitted or null fields are ignored.
If platform is set to switch and crossplay is omitted, crossplay is set to false.
If crossplay is true while the effective platform is switch, the request is rejected.
Response:
{
	"apiVersion": "x.x.x",
	"data": UserPrivate,
	"error": null
}

Data model inside is clickable: UserPrivate
​
POST  /v2/me/avatar ​
Update your avatar. The uploaded image is center-cropped to the target aspect ratio, resized to 256x256 pixels, encoded as WebP, and stored as the new avatar.
Request
Content-Type: multipart/form-data
form-data; name="avatar"; filename="whatever.png"

​
Request Fields
avatar file - Image file to upload as the new avatar.
Constraints
Accepts image formats: .png, .jpg, .jpeg, .webp, .gif, .bmp, .avif.
Maximum upload size is 5 MiB.
Response
{
	"apiVersion": "x.x.x",
	"data": UserPrivate,
	"error": null
}

Data model inside is clickable: UserPrivate
​
POST  /v2/me/background ​
Requires user to have at least a silver subscription tier.
Update your profile background. The uploaded image is center-cropped to the target aspect ratio, resized to 1920x820 pixels, encoded as WebP, and stored as the new background.
Request
Content-Type: multipart/form-data
form-data; name="background"; filename="whatever.png"

​
Request Fields
background file - Image file to upload as the new background.
Constraints
Accepts image formats: .png, .jpg, .jpeg, .webp, .gif, .bmp, .avif.
Maximum upload size is 8 MiB.
Response
{
	"apiVersion": "x.x.x",
	"data": UserPrivate,
	"error": null
}

Data model inside is clickable: UserPrivate
​
GET  /v2/user/{slug} 
GET  /v2/userId/{userId}
Get public information about a user. Users with role moderator and higher may receive moderation fields described in the User model.
URL parameters:
 slug - slug field from the User or UserShort model.
 userId - id field from the User or UserShort model.
Response:
{
	"apiVersion": "x.x.x",
	"data": User,
	"error": null
}

Data model inside: User
​
Achievements
GET  /v2/achievements ​
Get all available achievements. Secret achievements are omitted unless the requester has role admin.
Response:
{
	"apiVersion": "x.x.x",
	"data": [
		Achievement,
		Achievement,
		...
	],
	"error": null
}

Data model inside: Achievement, without state
​
GET  /v2/achievements/user/{slug} ​
GET  /v2/achievements/userId/{userId}
Get a user's achievements. Anonymous users and unrelated users do not receive hidden achievements. The requested user and users with role moderator and higher can receive hidden achievements.
URL parameters:
 slug - slug field from the User or UserShort model.
 userId - id field from the User or UserShort model.
Query parameters
 ▸  featured presence flag - When present, return only achievements where state.featured is true. The value is ignored, so ?featured=false still enables the filter.
Response:
{
	"apiVersion": "x.x.x",
	"data": [
		Achievement,
		Achievement,
		...
	],
	"error": null
}

Data model inside: Achievement, will include state
​
Authentication
POST  /auth/signin ​
Sign in with a first-party client and create a session.
First-party applications only. The client must be a registered first-party client and the request must pass Firebase App Check.
Headers
 Content-Type string - Must be application/json.
 X-Firebase-AppCheck string - Firebase App Check verification token.
Request body
{
	"email": "whatever@gmail.com",
	"password": "12345",
	"clientId": "wfm-0000",
	"deviceId": "random unique id",
	"deviceName": "My cool Nokia 3310"
}

​
Request Fields
Field
	
Type
	
Description


email
	
string
	
User email. Normalized to lowercase. Max: 128 characters.


password
	
string
	
User password. Min: 1 character for legacy compatibility. Max: 128 characters.


clientId
	
string
	
Registered first-party client id. Min: 6 characters. Max: 64 characters.


deviceId
	
string
	
Unique device id used to bind the session to this device. Min: 6 characters. Max: 256 characters.


deviceName
	
string
	
Human-readable device name. Defaults to Unknown. Max: 128 characters.
Response:
{
	"apiVersion": "x.x.x",
	"data": {
		"accessToken": "...",
		"refreshToken": "...",
		"tokenType": "Bearer",
		"expiresIn": 12345
	},
	"error": null
}

​
Response Fields
Field
	
Type
	
Description


accessToken
	
string
	
JWT access token for authenticated requests.


refreshToken
	
string
	
Refresh token for this session.


tokenType
	
"Bearer"
	
Token type for the Authorization header.


expiresIn
	
int
	
Access token lifetime in seconds.
POST  /auth/signup ​
Register a new user with a first-party client and create a session.
First-party applications only. The client must be a registered first-party client and the request must pass Firebase App Check.
Headers
 Content-Type string - Must be application/json.
 X-Firebase-AppCheck string - Firebase App Check verification token.
Request body
{
	"email": "whatever@gmail.com",
	"password": "123456",
	"passwordConfirmation": "123456",
	"clientId": "wfm-0000",
	"deviceId": "random unique id",
	"deviceName": "My Nokia 3310",
	"platform": "pc",
	"locale": "ko"
}

​
Request Fields
Field
	
Type
	
Description


email
	
string
	
User email. Normalized to lowercase. Max: 128 characters.


password
	
string
	
User password. Min: 6 characters. Max: 128 characters.


passwordConfirmation
	
string
	
Must match password. Min: 6 characters. Max: 128 characters.


clientId
	
string
	
Registered first-party client id. Min: 6 characters. Max: 64 characters.


deviceId
	
string
	
Unique device id used to bind the session to this device. Min: 6 characters. Max: 256 characters.


deviceName
	
string
	
Human-readable device name. Defaults to Unknown. Max: 128 characters.


platform
	
Platform
	
User's starting platform. Must be one of the supported platforms.


locale
	
Language
	
Preferred communication language.
Response:
{
	"apiVersion": "x.x.x",
	"data": {
		"accessToken": "...",
		"refreshToken": "...",
		"tokenType": "Bearer",
		"expiresIn": 12345
	},
	"error": null
}

​
POST  /auth/refresh
Refresh a session using a refresh token. This endpoint does not use the Authorization header.
First-party clients must include X-Firebase-AppCheck. Third-party clients do not use this header.
Headers
 Content-Type string - Must be application/json.
 X-Firebase-AppCheck string - Required only when clientId belongs to a first-party client.
Request body
{
	"grantType": "refresh_token",
	"clientId": "wfm-0000",
	"deviceId": "BASD001-KSADFDG",
	"refreshToken": "JwtRefreshToken"
}

​
Request Fields
Field
	
Type
	
Description


grantType
	
"refresh_token"
	
OAuth-style grant type for refresh-token flow.


clientId
	
string
	
Registered client id. Min: 6 characters. Max: 64 characters.


deviceId
	
string
	
Device id bound to the session. Min: 6 characters. Max: 256 characters.


refreshToken
	
string
	
Refresh token for the existing session. Min: 6 characters. Max: 256 characters.
Response:
{
	"apiVersion": "x.x.x",
	"data": {
		"accessToken": "...",
		"refreshToken": "...",
		"tokenType": "Bearer",
		"expiresIn": 12345
	},
	"error": null
}

​
POST  /auth/signout ​
Terminate the current session. The current access token and its session refresh tokens become unusable.
Requires:
Authentication
Headers
 Authorization string - JWT access token in format: Bearer YourJWTAccessToken.
Response
empty (no body), status code: 200
Dashboard
GET  /v2/dashboard/showcase ​
Mobile app main screen dashboard with featured items.
Response:
{
	"apiVersion": "x.x.x",
	"data": DashboardShowcase,
	"error": null
}

Data model inside is clickable: DashboardShowcase
​
OAuth

 /oauth/authorize - authorize request by 3rd party account
 /oauth/token - exchange code for access token, with PKCE
 /oauth/revoke - revoke access token